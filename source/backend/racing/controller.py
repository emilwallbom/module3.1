"""Local LMPC following Rosolia & Borrelli, TCST 28(6), 2020.

The default robust-lmpc is an explicit full-size adaptation: discrete nonlinear
prediction plus local residual regression and penalized terminal mismatch.
paper-hard and author-soft retain the paper's data-only identification for
comparison. No profile uses a centerline-curvature speed cap.
The local safe set/value function and velocity regressions use actual lap data.
"""
import math
import time
from types import SimpleNamespace
import clarabel
import numpy as np
import osqp
from scipy import sparse
from scipy.spatial import cKDTree
from .data import local_safe_set
from .vehicle import kinematic_linearization
from . import spec


class ControlFailure(RuntimeError):
    pass


def conic_fallback(cost, q, matrix, lower, upper, equality_rows):
    """Solve the identical convex QP with an interior-point method.

    OSQP is the normal fast path. This backup avoids treating ADMM convergence
    failures in nearly redundant terminal hulls as evidence of infeasibility.
    """
    inequalities=np.arange(len(lower))>=equality_rows
    highs=np.flatnonzero(inequalities & np.isfinite(upper))
    lows=np.flatnonzero(inequalities & np.isfinite(lower))
    a=sparse.vstack([matrix[:equality_rows],matrix[highs],-matrix[lows]],format="csc")
    b=np.r_[upper[:equality_rows],upper[highs],-lower[lows]]
    cones=[clarabel.ZeroConeT(equality_rows),clarabel.NonnegativeConeT(len(highs)),clarabel.NonnegativeConeT(len(lows))]
    settings=clarabel.DefaultSettings();settings.verbose=False;settings.max_iter=150
    settings.tol_feas=1e-7;settings.tol_gap_abs=1e-6;settings.tol_gap_rel=1e-6
    solution=clarabel.DefaultSolver(sparse.triu(cost,format="csc"),q,a,b,cones,settings).solve()
    return solution


class TrackingController:
    def __init__(self, vehicle, target_speed=8.0):
        self.vehicle, self.target_speed = vehicle, target_speed

    def solve(self, state):
        c, track = self.vehicle.config, self.vehicle.track
        _, _, _, curvature = track.reference(state[4]+max(2, state[0]*0.25))
        feedforward = math.atan((c.lf+c.lr)*curvature)
        delta = feedforward-0.8*state[3]-math.atan2(0.65*state[5], max(state[0], 3))-0.10*state[1]
        acceleration = 1.5*(self.target_speed-state[0])+0.00045*state[0]**2
        return np.clip([delta, acceleration], [-c.max_steer, -c.max_brake], [c.max_steer, c.max_accel])


class LearnedModel:
    def __init__(self, vehicle, laps, dt=0.1, regularized=False):
        self.vehicle, self.dt = vehicle, dt
        self.regularized = regularized
        rows, targets = [], []
        for lap in [l for l in laps if l.valid and l.kind in ("warmup", "learn")][-spec.HISTORY_LAPS:]:
            x, u = lap.arrays()
            rows.append(np.c_[x[:-1, :3], u])
            targets.append(x[1:, :3])
        self.rows = np.vstack(rows)
        self.targets = np.vstack(targets)
        self.tree = cKDTree(self.rows[:, :3]*np.array(spec.REGRESSION_METRIC))
        if regularized:
            self.scales = np.array([10.,3.,.6,.3,3.])
            self.support_tree = cKDTree(self.rows/self.scales)
            self.residual_targets=self.targets-vehicle.velocity_step_batch(self.rows[:,:3],self.rows[:,3:],dt)
            self.nominal_models={}

    def prepare(self, states, controls):
        """Linearize the discrete nonlinear step in a single vectorized batch.

        Unlike frozen-curvature Euler kinematics, this includes crossing an arc
        junction during the control period. Paper modes keep Eq. (12).
        """
        if not self.regularized:return
        query=np.c_[states,controls];points=[query.copy()];widths=[]
        for j in range(8):
            plus=query.copy();minus=query.copy();plus[:,j]+=1e-4;minus[:,j]-=1e-4
            if j>=6:
                limits=([-self.vehicle.config.max_steer,-self.vehicle.config.max_brake],
                        [self.vehicle.config.max_steer,self.vehicle.config.max_accel])
                plus[:,j]=np.minimum(plus[:,j],limits[1][j-6])
                minus[:,j]=np.maximum(minus[:,j],limits[0][j-6])
            widths.append(plus[:,j]-minus[:,j]);points.extend([plus,minus])
        batch=np.concatenate(points)
        values=self.vehicle.state_step_batch(batch[:,:6],batch[:,6:],self.dt).reshape(17,len(states),6)
        jacobian=np.stack([(values[1+2*j]-values[2+2*j])/widths[j][:,None] for j in range(8)],axis=2)
        offsets=values[0]-np.einsum('nij,nj->ni',jacobian,query)
        self.nominal_models={tuple(row):(jacobian[i,:,:6],jacobian[i,:,6:],offsets[i]) for i,row in enumerate(query)}

    def regularized_velocity_model(self, state, control):
        """Explicit full-size adaptation: residual correction to a nonlinear step.

        Outside measured state/input support the prior is used, rather than an
        ill-conditioned extrapolation of constant-speed warm-up data.
        """
        velocity=state[:3];key=tuple(np.r_[state,control])
        if key not in self.nominal_models:self.prepare(state[None,:],control[None,:])
        a,b,offset=(value.copy() for value in self.nominal_models[key])
        query=np.r_[velocity,control]
        distances,indices=self.support_tree.query(query/self.scales,k=min(80,len(self.rows)))
        distances,indices=np.atleast_1d(distances),np.atleast_1d(indices)
        weights=np.maximum(0.,1-(distances/.55)**2)
        for channel,input_index in [(0,1),(1,0),(2,0)]:
            columns=[0,1,2,3+input_index];scale=self.scales[columns]
            features=np.c_[(self.rows[indices][:,columns]-query[columns])/scale,np.ones(len(indices))]
            regularization=np.diag([25.,25.,25.,25.,2.])
            coefficients=np.linalg.solve(features.T@(weights[:,None]*features)+regularization,
                features.T@(weights*self.residual_targets[indices,channel]))
            correction_a=coefficients[:3]/scale[:3];correction_b=coefficients[3]/scale[3]
            a[channel,:3]+=correction_a;b[channel,input_index]+=correction_b
            offset[channel]+=coefficients[4]-correction_a@velocity-correction_b*control[input_index]
        return a,b,offset

    def neighbors(self, state):
        """Eq. (13): state-only Q-distance, P nearest, K(||dx||_Q² / h)."""
        distance, indices = self.tree.query(state[:3]*np.array(spec.REGRESSION_METRIC),
                                          k=min(spec.REGRESSION_NEIGHBORS, len(self.rows)))
        indices, distance = np.atleast_1d(indices), np.atleast_1d(distance)
        argument = distance**2 / spec.REGRESSION_BANDWIDTH
        weights = .75*np.maximum(0., 1.-argument**2)
        return indices[weights > 0], weights[weights > 0]

    def linearize(self, state, control):
        if self.regularized:
            return self.regularized_velocity_model(state,control)
        indices, weight = self.neighbors(state)
        if len(indices) < 5:
            raise ControlFailure(f"Identification has only {len(indices)} samples inside the paper kernel; no model substituted")
        av, bv, cv = np.zeros((3, 3)), np.zeros((3, 2)), np.zeros(3)
        for channel, input_index in [(0, 1), (1, 0), (2, 0)]:
            columns = [0, 1, 2, 3+input_index]
            # Center/scale only for numerical conditioning. With full column
            # rank this is exactly the unregularized weighted LS in Eq. (13).
            center = np.average(self.rows[indices][:, columns], axis=0, weights=weight)
            scale = np.maximum(np.std(self.rows[indices][:, columns], axis=0), 1e-8)
            features = np.c_[(self.rows[indices][:, columns]-center)/scale, np.ones(len(indices))]
            root = np.sqrt(weight)
            coefficients, _, rank, _ = np.linalg.lstsq(features*root[:, None],
                                                       self.targets[indices, channel]*root, rcond=1e-10)
            if rank < 5:
                raise ControlFailure(f"Local regression rank {rank}/5 for velocity channel {channel}; no nominal prior substituted")
            av[channel] = coefficients[:3]/scale[:3]
            bv[channel, input_index] = coefficients[3]/scale[3]
            cv[channel] = coefficients[4]-coefficients[:4]@(center/scale)
        a, b, offset = np.zeros((6, 6)), np.zeros((6, 2)), np.zeros(6)
        a[:3, :3], b[:3], offset[:3] = av, bv, cv
        curvature = self.vehicle.track.reference(state[4])[3]
        a[3:], offset[3:] = kinematic_linearization(state, curvature, self.dt)
        return a, b, offset


class LMPC:
    def __init__(self, vehicle, horizon=None, dt=spec.DT, terminal_mode=spec.DEFAULT_PROFILE):
        if terminal_mode not in spec.PROFILES:
            raise ValueError("Unknown terminal mode")
        if horizon is None:horizon=spec.ROBUST_HORIZON if terminal_mode=="robust-lmpc" else spec.HORIZON
        self.terminal_mode = terminal_mode
        self.vehicle, self.N, self.dt = vehicle, horizon, dt
        self.prediction = None
        self.controls = None
        self.candidate = None
        self.candidate_input = None
        self.last_input = np.zeros(2)
        self.diagnostics = {"status": "initializing", "milliseconds": 0., "terminal_slack": 0.}
        self.samples = np.zeros((6, 0))
        self.last_lambda = None
        self.model_cache = None
        self.model_key = None

    def new_lap(self):
        self.prediction = self.controls = self.candidate = self.candidate_input = None
        self.last_lambda = None

    def solve(self, state, laps):
        started = time.perf_counter()
        try:
            try:
                result = self._solve(state, laps)
                self.diagnostics["relinearizations"] = 0
            except ControlFailure:
                # Numerical/model retry, explicitly outside the paper equations.
                self.new_lap()
                result = self._solve(state, laps)
                self.diagnostics["relinearizations"] = 1
        except ControlFailure as error:
            self.diagnostics = {"status": str(error), "milliseconds": (time.perf_counter()-started)*1000,
                                "terminal_mode":self.terminal_mode,"horizon":self.N,
                                "terminal_samples":self.samples.shape[1],"terminal_slack":0.,
                                "failed":True,"relinearizations":1}
            raise
        self.diagnostics["milliseconds"] = (time.perf_counter()-started)*1000
        self.diagnostics["over_budget"] = self.diagnostics["milliseconds"] > self.dt*1000
        return result

    def _solve(self, state, laps):
        started = time.perf_counter()
        n, d, N = 6, 2, self.N
        relevant=[lap for lap in laps if lap.valid and lap.kind in ("learn","warmup")][-spec.HISTORY_LAPS:]
        key=tuple((id(lap),len(lap.u),len(lap.ext_x)) for lap in relevant)
        if self.model_cache is None or key!=self.model_key:
            self.model_cache=LearnedModel(self.vehicle,laps,self.dt,regularized=self.terminal_mode=="robust-lmpc")
            self.model_key=key
        model=self.model_cache
        if self.prediction is None:
            previous = [lap for lap in laps if lap.valid and lap.kind in ("learn", "warmup")][-1]
            data, inputs = previous.arrays()
            index = int(np.argmin(abs(data[:, 4]-state[4])))
            indices = np.clip(np.arange(index, index+N+1), 0, len(data)-1)
            bar = data[indices].copy()
            ubar = inputs[np.clip(indices[:-1], 0, len(inputs)-1)].copy()
            self.candidate = bar[-1].copy()
        else:
            # Section IV-C: append the safe-set successor, not a repeated endpoint.
            bar = np.vstack([self.prediction[1:], self.candidate])
            ubar = np.vstack([self.controls[1:], self.candidate_input])
        bar[0] = state
        if self.terminal_mode=="robust-lmpc":
            ubar=np.clip(ubar,[-self.vehicle.config.max_steer,-self.vehicle.config.max_brake],
                          [self.vehicle.config.max_steer,self.vehicle.config.max_accel])
            model.prepare(bar[:-1],ubar)
        terminal, successors, costs, successor_inputs = local_safe_set(laps, self.candidate[4], include_inputs=True)
        self.samples = terminal
        # Translate progress to the current vehicle position. Without this exact
        # change of variables the terminal columns grow to hundreds of metres
        # and unnecessarily degrade QP conditioning near the finish line.
        origin = np.zeros(n); origin[4] = state[4]
        m = terminal.shape[1]
        nx, nu = (N+1)*n, N*d
        il, iz = nx+nu, nx+nu+m
        relaxed=self.terminal_mode!="paper-hard"
        islip = iz+(n if relaxed else 0)
        size = islip+(2*N if self.terminal_mode=="robust-lmpc" else 0)
        cost = sparse.lil_matrix((size, size))
        q = np.zeros(size)
        # Input increments make the solution unique without prescribing a racing line.
        rate = np.array([10.,.05] if self.terminal_mode=="robust-lmpc" else spec.INPUT_RATE_WEIGHTS)
        for k in range(N):
            for j in range(d):
                i = nx+k*d+j
                cost[i, i] += 2*rate[j]
                if k:
                    cost[i-d, i-d] += 2*rate[j]
                    cost[i, i-d] -= 2*rate[j]
                    cost[i-d, i] -= 2*rate[j]
                else:
                    q[i] -= 2*rate[j]*self.last_input[j]
        q[il:iz] = costs
        if relaxed:
            # Explicit author-repository relaxation, not Eq. (8c) in the paper.
            cost[iz:islip, iz:islip] = sparse.eye(n)*1000.  # 500 ||sigma||²
        if size>islip:
            cost[islip:,islip:]=sparse.eye(2*N)*2*spec.ROBUST_SLIP_PENALTY
        eq = sparse.lil_matrix((n*(N+2)+1, size))
        rhs = np.zeros(eq.shape[0])
        eq[:n, :n] = sparse.eye(n); rhs[:n] = state-origin
        for k in range(N):
            a, b, offset = model.linearize(bar[k], ubar[k])
            row = n*(k+1)
            eq[row:row+n, k*n:(k+1)*n] = -a
            eq[row:row+n, (k+1)*n:(k+2)*n] = sparse.eye(n)
            eq[row:row+n, nx+k*d:nx+(k+1)*d] = -b
            rhs[row:row+n] = offset+a@origin-origin
        row = n*(N+1)
        eq[row:row+n, N*n:(N+1)*n] = sparse.eye(n)
        eq[row:row+n, il:iz] = -(terminal-origin[:, None])
        if relaxed:
            eq[row:row+n, iz:islip] = -sparse.eye(n)
        eq[-1, il:iz] = np.ones(m); rhs[-1] = 1
        # Box bounds plus a conservative four-plane footprint envelope.
        lower, upper = np.full(size, -np.inf), np.full(size, np.inf)
        c = self.vehicle.config
        for k in range(1, N+1):
            # Fixed full-size operating limits, not curvature- or data-dependent
            # velocity envelopes. The velocity model comes entirely from data.
            lower[k*n:k*n+6] = [0.5, -np.inf, -np.inf, -np.pi/2, -np.inf, -np.inf]
            upper[k*n:k*n+6] = [c.max_speed, np.inf, np.inf, np.pi/2, np.inf, np.inf]
        lower[nx:il] = np.tile([-c.max_steer, -c.max_brake], N)
        upper[nx:il] = np.tile([c.max_steer, c.max_accel], N)
        lower[il:iz], upper[il:iz] = 0, 1
        lower[islip:] = 0.
        footprint = sparse.lil_matrix((N*4, size))
        for k in range(1, N+1):
            for j, (se, sy) in enumerate([(-1,-1), (-1,1), (1,-1), (1,1)]):
                footprint[(k-1)*4+j, k*n+3] = se*c.length/2
                footprint[(k-1)*4+j, k*n+5] = sy
        matrix = sparse.vstack([eq, sparse.eye(size), footprint], format="csc")
        lb = np.r_[rhs, lower, np.full(N*4, -np.inf)]
        ub = np.r_[rhs, upper, np.full(N*4, self.vehicle.track.width/2-c.width/2+c.width*spec.TRACK_OVERHANG_FRACTION)]
        if self.terminal_mode=="robust-lmpc":
            increments=sparse.lil_matrix((N,size))
            for k in range(N):
                increments[k,nx+k*d]=1.
                if k:increments[k,nx+(k-1)*d]=-1.
            center=np.zeros(N);center[0]=self.last_input[0]
            matrix=sparse.vstack([matrix,increments],format="csc")
            lb=np.r_[lb,center-spec.ROBUST_STEERING_RATE*self.dt]
            ub=np.r_[ub,center+spec.ROBUST_STEERING_RATE*self.dt]
            # Penalize operation beyond a tire-force working range using the
            # predicted vehicle state. This is independent of track curvature;
            # a larger trajectory radius can still support a higher speed.
            slips=sparse.lil_matrix((4*N,size));slip_upper=np.zeros(4*N)
            for k in range(N):
                vx=max(bar[k,0],1.5)
                for axle,arm,stiffness,load_fraction in [(0,c.lf,c.stiffness_front,c.lr/(c.lf+c.lr)),
                                                        (1,-c.lr,c.stiffness_rear,c.lf/(c.lf+c.lr))]:
                    lateral=bar[k,1]+arm*bar[k,2];den=vx*vx+lateral*lateral
                    gradient=np.array([-lateral/den,vx/den,arm*vx/den])
                    center=math.atan2(lateral,vx)-gradient@bar[k,:3]
                    limit=math.atanh(spec.ROBUST_TIRE_UTILIZATION)*c.friction*c.mass*9.81*load_fraction/stiffness
                    for sign in (-1,1):
                        row=4*k+2*axle+(1 if sign==1 else 0)
                        slips[row,k*n:k*n+3]=-sign*gradient
                        if axle==0:slips[row,nx+k*d]=sign
                        slips[row,islip+2*k+axle]=-1.
                        slip_upper[row]=limit+sign*center
            matrix=sparse.vstack([matrix,slips],format="csc")
            lb=np.r_[lb,np.full(4*N,-np.inf)];ub=np.r_[ub,slip_upper]
        solver = osqp.OSQP()
        solver.setup(P=cost.tocsc(), q=q, A=matrix, l=lb, u=ub,
                     verbose=False, eps_abs=1e-4, eps_rel=1e-4, max_iter=15000,
                     polishing=True, adaptive_rho=True, eps_prim_inf=1e-6, eps_dual_inf=1e-6)
        initial_lambda = np.full(m, 1/m) if self.last_lambda is None or len(self.last_lambda) != m else self.last_lambda
        solver.warm_start(x=np.r_[(bar-origin).ravel(), ubar.ravel(), initial_lambda,
                                 np.zeros(size-iz)])
        result = solver.solve(raise_error=False)
        elapsed = (time.perf_counter()-started)*1000
        violation = np.inf if result.x is None else max(float(np.max(lb-matrix@result.x)), float(np.max(matrix@result.x-ub)))
        feasible_limit = (result.info.status_val == 7 and violation < 0.005
                          and result.info.prim_res < 0.005 and result.info.dual_res < 0.005)
        primary_status=result.info.status
        solver_used="osqp"
        if result.x is None or (result.info.status_val not in (1,2) and not feasible_limit):
            backup=conic_fallback(cost.tocsc(),q,matrix,lb,ub,eq.shape[0])
            if str(backup.status) in ("Solved","AlmostSolved"):
                solver_used="clarabel"
                result=SimpleNamespace(x=np.asarray(backup.x),info=SimpleNamespace(status="clarabel "+str(backup.status),
                    status_val=1,prim_res=backup.r_prim,dual_res=backup.r_dual,iter=backup.iterations))
                violation=max(float(np.max(lb-matrix@result.x)),float(np.max(matrix@result.x-ub)))
                feasible_limit=False
                elapsed=(time.perf_counter()-started)*1000
        if result.x is None or (result.info.status_val not in (1, 2) and not feasible_limit):
            self.diagnostics = {"status": result.info.status, "milliseconds": elapsed, "terminal_slack": 0.}
            raise ControlFailure(f"LMPC QP: {result.info.status}; primal={result.info.prim_res:.4g}, dual={result.info.dual_res:.4g}")
        if not np.all(np.isfinite(result.x)) or violation > 0.015:
            raise ControlFailure(f"QP constraint residual {violation:.4f}")
        self.prediction = result.x[:nx].reshape(N+1, n)+origin
        self.controls = result.x[nx:il].reshape(N, d)
        self.last_lambda = result.x[il:iz]
        self.candidate = successors@self.last_lambda
        self.candidate_input = successor_inputs@self.last_lambda
        self.last_input = self.controls[0].copy()
        self.diagnostics = {"status": result.info.status, "milliseconds": elapsed,
                            "solver": solver_used, "primary_status": primary_status,
                            "terminal_slack": float(np.linalg.norm(result.x[iz:islip])),
                            "tire_range_slack": float(np.max(result.x[islip:])) if size>islip else 0.,
                            "terminal_mode": self.terminal_mode,
                            "terminal_residual": float(np.linalg.norm(self.prediction[-1]-terminal@self.last_lambda)),
                            "horizon": N, "terminal_samples": m,
                            "accepted_feasible_iteration_limit": bool(feasible_limit),
                            "dual_residual": float(result.info.dual_res),
                            "residual": violation, "iterations": int(result.info.iter),
                            "over_budget": elapsed > self.dt*1000}
        return self.last_input.copy()

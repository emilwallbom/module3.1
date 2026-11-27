"""Approximate C4-sized dynamic bicycle; the same plant is used in every mode."""
from dataclasses import asdict, dataclass
import math
import numpy as np
from .track import Track
from . import spec


@dataclass(frozen=True)
class VehicleConfig:
    mass: float = 1500.0
    inertia: float = 2500.0
    lf: float = 1.22
    lr: float = 1.22
    length: float = 4.48
    width: float = 1.80
    friction: float = 0.95
    stiffness_front: float = 70000.0
    stiffness_rear: float = 80000.0
    max_steer: float = 0.5
    max_accel: float = 3.0
    max_brake: float = 7.0
    max_speed: float = 36.0


class Vehicle:
    def __init__(self, track: Track, config=None):
        self.track, self.config = track, config or VehicleConfig()

    def velocity_derivative(self, velocity, control):
        vx, vy, yaw = velocity
        delta, acceleration = control
        c = self.config
        speed = max(vx, 1.5)
        front_limit = c.friction*c.mass*9.81*c.lr/(c.lf+c.lr)
        rear_limit = c.friction*c.mass*9.81*c.lf/(c.lf+c.lr)
        fyf = front_limit*math.tanh(c.stiffness_front*(delta-math.atan2(vy+c.lf*yaw, speed))/front_limit)
        fyr = rear_limit*math.tanh(c.stiffness_rear*(-math.atan2(vy-c.lr*yaw, speed))/rear_limit)
        dx = acceleration-fyf*math.sin(delta)/c.mass+yaw*vy-0.00045*vx*abs(vx)
        dy = (fyf*math.cos(delta)+fyr)/c.mass-yaw*vx
        dr = (c.lf*fyf*math.cos(delta)-c.lr*fyr)/c.inertia
        # Smooth relaxation to kinematic behavior near standstill avoids slip-angle singularities.
        blend = min(1.0, max(0.0, (vx-0.3)/2.2))
        target_yaw = vx*math.tan(delta)/(c.lf+c.lr)
        target_vy = c.lr*target_yaw
        return np.array([dx, blend*dy+(1-blend)*(target_vy-vy)*8,
                         blend*dr+(1-blend)*(target_yaw-yaw)*8])

    def _derivative(self, world, control):
        px, py, heading, vx, vy, yaw = world
        vx = max(0.0, vx)
        velocities = self.velocity_derivative((vx, vy, yaw), control)
        return np.array([vx*math.cos(heading)-vy*math.sin(heading),
                         vx*math.sin(heading)+vy*math.cos(heading), yaw, *velocities])

    def velocity_step_batch(self, velocities, controls, dt=.1):
        """Vectorized nominal transitions for residual identification; same RK4 plant."""
        world=np.c_[np.zeros((len(velocities),3)),velocities]
        return self.world_step_batch(world,controls,dt)[:,3:]

    def world_step_batch(self, worlds, controls, dt=.1):
        c=self.config;world=np.array(worlds,dtype=float,copy=True)
        u=np.clip(controls,[-c.max_steer,-c.max_brake],[c.max_steer,c.max_accel])
        def derivative(values):
            vx=np.maximum(values[:,3],0.);vy=values[:,4];yaw=values[:,5];heading=values[:,2]
            delta=u[:,0];speed=np.maximum(vx,1.5)
            front=c.friction*c.mass*9.81*c.lr/(c.lf+c.lr)
            rear=c.friction*c.mass*9.81*c.lf/(c.lf+c.lr)
            fyf=front*np.tanh(c.stiffness_front*(delta-np.arctan2(vy+c.lf*yaw,speed))/front)
            fyr=rear*np.tanh(-c.stiffness_rear*np.arctan2(vy-c.lr*yaw,speed)/rear)
            blend=np.clip((vx-.3)/2.2,0.,1.)
            target=vx*np.tan(delta)/(c.lf+c.lr)
            return np.c_[vx*np.cos(heading)-vy*np.sin(heading),vx*np.sin(heading)+vy*np.cos(heading),yaw,
                u[:,1]-fyf*np.sin(delta)/c.mass+yaw*vy-.00045*vx*np.abs(vx),
                blend*((fyf*np.cos(delta)+fyr)/c.mass-yaw*vx)+(1-blend)*(c.lr*target-vy)*8,
                blend*((c.lf*fyf*np.cos(delta)-c.lr*fyr)/c.inertia)+(1-blend)*(target-yaw)*8]
        substeps=max(1,round(dt/.005));h=dt/substeps
        for _ in range(substeps):
            k1=derivative(world);k2=derivative(world+h/2*k1);k3=derivative(world+h/2*k2);k4=derivative(world+h*k3)
            world+=h/6*(k1+2*k2+2*k3+k4);world[:,3]=np.maximum(world[:,3],0.)
            world[(world[:,3]<.02)&(u[:,1]<=0),3:]*=.5
        return world

    def state_step_batch(self, states, controls, dt=.1):
        """Nominal nonlinear Frenet transitions, including curvature junctions."""
        reference=self.track.reference_many(states[:,4]);tangent=reference[:,2]
        world=np.c_[reference[:,0]-np.sin(tangent)*states[:,5],
                    reference[:,1]+np.cos(tangent)*states[:,5],tangent+states[:,3],states[:,:3]]
        next_world=self.world_step_batch(world,controls,dt)
        guess=states[:,4]+dt*(states[:,0]*np.cos(states[:,3])-states[:,1]*np.sin(states[:,3]))/(1-reference[:,3]*states[:,5])
        position=self.track.project_many(next_world[:,0],next_world[:,1],next_world[:,2],guess)
        return np.c_[next_world[:,3:],position]

    def initial(self, speed=8.0):
        return np.array([0., 0., 0., speed, 0., 0.])

    def state(self, world, previous_s=0):
        local = self.track.project(*world[:3], previous_s)
        return np.r_[world[3:], local]

    def step(self, world, control, dt=0.1):
        c = self.config
        control = np.clip(control, [-c.max_steer, -c.max_brake], [c.max_steer, c.max_accel])
        result = world.copy()
        substeps = max(1, round(dt/0.005))
        h = dt/substeps
        for _ in range(substeps):
            k1 = self._derivative(result, control)
            k2 = self._derivative(result+h/2*k1, control)
            k3 = self._derivative(result+h/2*k2, control)
            k4 = self._derivative(result+h*k3, control)
            result += h/6*(k1+2*k2+2*k3+k4)
            result[3] = max(0.0, result[3])
            if result[3] < 0.02 and control[1] <= 0:
                result[3:] *= 0.5
        if not np.all(np.isfinite(result)):
            raise FloatingPointError("Vehicle state became non-finite")
        return result

    def footprint_margin(self, state):
        c = self.config
        extent = abs(math.sin(state[3]))*c.length/2+abs(math.cos(state[3]))*c.width/2
        # User-defined racing limit: at most half the car width beyond either
        # road edge. The projected length still matters when the car is yawed.
        return self.track.width/2+c.width*spec.TRACK_OVERHANG_FRACTION-abs(state[5])-extent

    def identity(self):
        return asdict(self.config)


def kinematic_linearization(state, curvature, dt=0.1):
    """Frenet equations and their Jacobian; order is epsi, s, ey."""
    vx, vy, r, e, s, ey = state
    co, si = math.cos(e), math.sin(e)
    denominator = 1-curvature*ey
    if abs(denominator) < 0.1:
        raise ValueError("Frenet coordinate singularity")
    longitudinal = vx*co-vy*si
    lateral = vx*si+vy*co
    jac = np.zeros((3, 6))
    ds = np.array([co/denominator, -si/denominator, 0, -lateral/denominator, 0,
                   longitudinal*curvature/denominator**2])
    jac[0] = -curvature*ds
    jac[0, 2] += 1
    jac[1] = ds
    jac[2] = [si, co, 0, longitudinal, 0, 0]
    jac *= dt
    jac[:, 3:] += np.eye(3)
    value = state[3:]+dt*np.array([r-curvature*longitudinal/denominator,
                                  longitudinal/denominator, lateral])
    return jac, value-jac@state

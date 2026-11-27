import json
import numpy as np
import pytest
from racing.controller import ControlFailure, LearnedModel
from racing.data import Lap, Repository, local_safe_set
from racing.session import Run, Session


@pytest.fixture(scope="module")
def initialized():
    run=Run(seed=7,terminal_mode="paper-hard")
    while len(run.laps)<2 and not run.paused:run.step()
    assert not run.paused
    return run


def test_safe_set_barycentric_cost_and_manual_exclusion(initialized):
    terminal,successors,cost=local_safe_set(initialized.laps,50.)
    assert terminal.shape==(6,40) and successors.shape==(6,40)
    weights=np.full(40,1/40)
    assert np.isfinite(cost@weights)
    assert np.all(successors[4]>terminal[4])
    manual=Lap(3,"drive",initialized.laps[0].x,initialized.laps[0].u,initialized.laps[0].poses)
    rejected=Lap(4,"learn",manual.x,manual.u,manual.poses,valid=False)
    other=local_safe_set(initialized.laps+[manual,rejected],50.)
    for expected,actual in zip((terminal,successors,cost),other):np.testing.assert_array_equal(expected,actual)
    for index in [0,19,20,39]:
        lap=initialized.laps[index//20]
        row=np.argmin(np.linalg.norm(lap.x-terminal[:,index],axis=1))
        assert cost[index]==len(lap.u)-row


def test_velocity_regression_responds_to_measured_data(initialized):
    model=LearnedModel(initialized.vehicle,initialized.laps)
    state=initialized.laps[0].x[30];control=initialized.laps[0].u[30]
    a,b,c=model.linearize(state,control)
    before=(a@state+b@control+c)[0]
    model.targets[:,0]+=0.3
    a,b,c=model.linearize(state,control)
    assert (a@state+b@control+c)[0]>before+.1


def test_regression_rejects_missing_data_without_substituting_prior(initialized):
    model=LearnedModel(initialized.vehicle,initialized.laps)
    state=np.array([30.,8.,2.,0.,30.,0.]);control=np.array([.45,3.])
    with pytest.raises(ControlFailure,match="no model substituted"):
        model.linearize(state,control)


def test_paper_regression_matches_equation_13(initialized):
    from racing import spec
    model=LearnedModel(initialized.vehicle,initialized.laps)
    state=initialized.laps[0].x[30];control=initialized.laps[0].u[30]
    distances=np.linalg.norm((model.rows[:,:3]-state[:3])*np.array([.1,1.,1.]),axis=1)
    indices=np.argsort(distances)[:80]
    weights=.75*np.maximum(0.,1-(distances[indices]**2/10.)**2)
    a,b,c=model.linearize(state,control)
    for channel,input_index in [(0,1),(1,0),(2,0)]:
        features=np.c_[model.rows[indices][:,[0,1,2,3+input_index]],np.ones(len(indices))]
        expected=np.linalg.lstsq(features*np.sqrt(weights[:,None]),
                                  model.targets[indices,channel]*np.sqrt(weights),rcond=None)[0]
        np.testing.assert_allclose(np.r_[a[channel,:3],b[channel,input_index],c[channel]],expected,atol=1e-6)
    # The input does not participate in neighbor selection in the paper.
    alternative=model.linearize(state,control+np.array([.3,2.]))
    for before,after in zip((a,b,c),alternative):np.testing.assert_allclose(before,after)
    assert spec.HORIZON==12 and spec.TERMINAL_SAMPLES_PER_LAP==20


def test_full_lmpc_falls_back_to_same_qp(initialized,monkeypatch):
    import copy
    from types import SimpleNamespace
    import osqp
    run=copy.deepcopy(initialized)
    def fail(*args,**kwargs):
        return SimpleNamespace(x=None,info=SimpleNamespace(status="injected convergence failure",status_val=7,prim_res=1.,dual_res=1.,iter=0))
    monkeypatch.setattr(osqp.OSQP,"solve",fail)
    control=run.controller.solve(run.local_state(),run.laps)
    assert run.controller.diagnostics["solver"]=="clarabel"
    assert run.controller.diagnostics["residual"]<1e-5
    assert abs(control[0])<=.5001 and -7.001<=control[1]<=3.001


def test_qp_constraints_and_candidate_successor(initialized):
    import copy
    run=copy.deepcopy(initialized)
    data,_=run.laps[-1].arrays()
    index=np.argmin(abs(data[:,4]-run.local_state()[4]))
    center=data[min(index+run.controller.N,len(data)-1),4]
    terminal,successors,cost,successor_inputs=local_safe_set(run.laps,center,include_inputs=True)
    control=run.controller.solve(run.local_state(),run.laps)
    assert abs(control[0])<=.5001 and -7.01<=control[1]<=3.01
    assert run.controller.diagnostics["residual"]<.015
    weights=run.controller.last_lambda
    assert weights.min()>-1e-3 and abs(weights.sum()-1)<1e-3
    np.testing.assert_allclose(run.controller.candidate,successors@weights)
    np.testing.assert_allclose(run.controller.candidate_input,successor_inputs@weights)
    assert run.controller.diagnostics["status"] in ("solved","solved inaccurate")
    assert run.controller.diagnostics["terminal_mode"]=="paper-hard"
    assert run.controller.diagnostics["terminal_slack"]==0
    assert run.controller.diagnostics["terminal_residual"]<.001
    assert run.controller.N==12 and run.controller.samples.shape[1]==40


def test_terminal_profiles_have_separate_checkpoint_identity():
    strict=Run(terminal_mode="paper-hard");soft=Run(terminal_mode="author-soft");robust=Run()
    assert len({strict.identity,soft.identity,robust.identity})==3


def test_robust_controller_solves_recorded_v2_terminal_deadend():
    from pathlib import Path
    from racing.controller import LMPC
    from racing.vehicle import Vehicle
    from racing.track import Track
    laps=[]
    with np.load(Path(__file__).parent/'fixtures/terminal_deadend_v2.npz') as data:
        for j in range(2):
            x=data[f'{j}_x'];u=data[f'{j}_u']
            lap=Lap(j+1,'warmup' if j==0 else 'learn',x,u,np.zeros((len(x),3)))
            lap.ext_x=list(data[f'{j}_ext_x']);lap.ext_u=list(data[f'{j}_ext_u']);laps.append(lap)
        state=data['state'];last=data['control']
    controller=LMPC(Vehicle(Track()));controller.last_input=last.copy()
    control=controller.solve(state,laps)
    assert controller.diagnostics['terminal_mode']=='robust-lmpc'
    assert controller.diagnostics['residual']<.001
    assert np.isfinite(controller.diagnostics['terminal_slack'])
    assert abs(control[0]-last[0])<=.0701


def test_residual_model_matches_nonlinear_step_at_junction(initialized):
    model=LearnedModel(initialized.vehicle,initialized.laps,regularized=True)
    state=np.array([18.3,.81,.161,.28,154.983,1.81]);control=np.array([.0524,1.144])
    a,b,c=model.linearize(state,control)
    truth=initialized.vehicle.state_step_batch(state[None,:],control[None,:])[0]
    np.testing.assert_allclose(a@state+b@control+c,truth,atol=1e-8)


def test_historical_replay_cannot_seed_current_learner(initialized,tmp_path):
    repository=Repository(tmp_path/"old",{"algorithm_revision":"legacy-test"},"legacy-test")
    repository.save(initialized.laps,{})
    session=Session(directory=tmp_path/"current")
    original=session.learn.world.copy()
    session.load_external_replay(tmp_path/"old")
    assert session.mode=="replay" and "LEGACY" in session.frame()["controller_profile"]
    assert len(session.ghosts())==3 and session.learn.laps==[]
    for _ in range(10):session.step()
    np.testing.assert_array_equal(session.learn.world,original)
    session.command({"command":"mode","value":"learn"})
    assert session.learn.laps==[] and session.external_replay_laps is None
    assert session.frame()["controller_profile"]=="robust-lmpc"


def test_current_recording_replay_is_labeled_and_read_only(initialized,tmp_path):
    from racing.data import config_identity
    config,identity=config_identity(initialized.track,initialized.vehicle,terminal_mode="paper-hard")
    Repository(tmp_path/"recorded",config,identity).save(initialized.laps,{})
    session=Session(directory=tmp_path/"live")
    original=session.learn.world.copy();original_identity=session.learn.identity
    session.load_external_replay(tmp_path/"recorded")
    assert session.frame()["controller_profile"]=="REPLAY paper-hard"
    for _ in range(10):session.step()
    np.testing.assert_array_equal(session.learn.world,original)
    assert session.learn.identity==original_identity and session.learn.laps==[]


def test_no_centerline_or_observed_speed_cap_in_qp(initialized,monkeypatch):
    import copy,osqp
    run=copy.deepcopy(initialized)
    original=osqp.OSQP.setup
    captured={}
    def setup(self,*args,**kwargs):
        captured.update(kwargs)
        return original(self,*args,**kwargs)
    monkeypatch.setattr(osqp.OSQP,"setup",setup)
    run.controller.solve(run.local_state(),run.laps)
    equality_rows=6*(run.controller.N+2)+1
    indices=equality_rows+np.arange(1,run.controller.N+1)*6
    np.testing.assert_array_equal(captured['u'][indices],run.vehicle.config.max_speed)


def test_failed_attempt_is_rejected_and_can_retry(initialized,monkeypatch):
    import copy
    run=copy.deepcopy(initialized)
    start_control=run.last_input.copy()
    previous=[lap.x.copy() for lap in run.laps]
    def fail(*args):raise ControlFailure("injected solver failure")
    monkeypatch.setattr(run.controller,"solve",fail)
    lap=run.step()
    assert run.paused and not lap.valid and "injected" in lap.reason
    assert run.learning_laps==0
    assert run.solver_events[-1]['event']=='attempt_rejected'
    for before,after in zip(previous,run.laps):np.testing.assert_array_equal(before,after.x)
    run.recover()
    assert not run.paused and run.failure==""
    np.testing.assert_array_equal(run.last_input,start_control)


def test_manual_and_replay_do_not_advance_training(tmp_path):
    session=Session(directory=tmp_path)
    original=session.learn.world.copy()
    original_rng=json.dumps(session.learn.rng.bit_generator.state)
    session.command({"command":"mode","value":"drive"})
    session.command({"command":"control","value":[.1,3]})
    for _ in range(30):session.step()
    np.testing.assert_array_equal(session.learn.world,original)
    assert json.dumps(session.learn.rng.bit_generator.state)==original_rng
    assert session.learn.laps==[] and session.manual.world[3]>1
    session.command({"command":"mode","value":"replay"})
    session.command({"command":"pause","value":True})
    assert session.replay_paused and not session.learn.paused
    with pytest.raises(ValueError):session.command({"command":"control","value":[float("nan"),0]})


def test_checkpoint_round_trip_and_configuration_rejection(initialized,tmp_path):
    import copy
    run=copy.deepcopy(initialized)
    config=run.vehicle.identity()
    from racing.data import config_identity
    config,identity=config_identity(run.track,run.vehicle,terminal_mode="paper-hard")
    run.repository=Repository(tmp_path,config,identity)
    run.save()
    restored=Run(seed=7,directory=tmp_path,terminal_mode="paper-hard");restored.load()
    np.testing.assert_array_equal(restored.world,run.world)
    for before,after in zip(run.laps,restored.laps):
        np.testing.assert_array_equal(before.x,after.x)
        assert before.seconds==after.seconds
    with pytest.raises(ValueError,match="does not match"):
        Run(track="oval",directory=tmp_path).load()
    assert (tmp_path/"laps.csv").exists()


def test_replay_interpolation_and_historical_ghost(initialized,tmp_path):
    import copy
    session=Session(directory=tmp_path)
    session.learn=copy.deepcopy(initialized)
    session.command({"command":"replay","lap":1})
    session.command({"command":"mode","value":"replay"})
    session.command({"command":"pause","value":True})
    session.command({"command":"seek","value":1.05})
    frame=session.frame()
    expected=(session.replay_lap.poses[10]+session.replay_lap.poses[11])/2
    np.testing.assert_allclose(frame["pose"],expected,atol=1e-9)
    assert frame["paused"] and not session.learn.paused
    assert frame["replay_duration"]==session.replay_lap.seconds
    session.command({"command":"ghost","lap":1})
    ghosts=session.ghosts()
    assert len(ghosts)==3 and ghosts[-1]["number"]==1
    with pytest.raises(ValueError):session.command({"command":"ghost","lap":999})

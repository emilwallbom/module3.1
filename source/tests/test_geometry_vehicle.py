import math
import numpy as np
import pytest
from racing.track import Track, wrap
from racing.vehicle import Vehicle, kinematic_linearization


@pytest.mark.parametrize("name", ["l_track", "oval"])
def test_closed_track_projection_round_trip(name):
    track = Track(name)
    assert np.linalg.norm(np.array(track.reference(0)[:2])-np.array(track.reference(track.length)[:2])) < 1e-8
    for s in np.linspace(0.3, track.length-0.3, 73):
        for lateral in [-2., 0., 2.]:
            state = np.array([10., 0., 0., 0.12, s+2*track.length, lateral])
            pose = track.global_pose(state)
            projected = track.project(*pose, state[4])
            np.testing.assert_allclose(projected, state[3:], atol=1e-3)


def test_finish_line_unwrap_and_footprint():
    track = Track(); vehicle = Vehicle(track)
    state = np.array([8,0,0,0,track.length+0.2,0.])
    assert track.project(*track.global_pose(state),track.length-0.1)[1] > track.length
    assert vehicle.footprint_margin(state) > 3
    state[5] = 4.
    assert abs(vehicle.footprint_margin(state)) < 1e-10
    state[5] = 4.02
    assert vehicle.footprint_margin(state) < 0


@pytest.mark.parametrize("side",[-1,1])
def test_half_width_overhang_and_rotated_footprint(side):
    vehicle=Vehicle(Track())
    state=np.array([8.,0.,0.,0.,30.,side*4.])
    assert abs(vehicle.footprint_margin(state))<1e-10
    state[5]=side*3.5;state[3]=.2
    assert vehicle.footprint_margin(state)>0
    state[5]=side*4.
    assert vehicle.footprint_margin(state)<0  # Front corner exceeds 0.9 m.


def test_batch_nominal_velocities_match_actual_plant():
    vehicle=Vehicle(Track());rng=np.random.default_rng(4)
    velocities=np.c_[rng.uniform(0,24,12),rng.uniform(-1,1,12),rng.uniform(-.8,.8,12)]
    controls=np.c_[rng.uniform(-.4,.4,12),rng.uniform(-7,3,12)]
    actual=np.array([vehicle.step(np.r_[0.,0.,0.,v],u)[3:] for v,u in zip(velocities,controls)])
    np.testing.assert_allclose(vehicle.velocity_step_batch(velocities,controls),actual,atol=1e-10)


def test_prediction_crosses_curvature_sign_junction():
    vehicle=Vehicle(Track())
    state=np.array([18.3,.81,.161,.28,154.983,1.81]);control=np.array([.0524,1.144])
    world=np.r_[vehicle.track.global_pose(state),state[:3]]
    truth=vehicle.state(vehicle.step(world,control),state[4])
    predicted=vehicle.state_step_batch(state[None,:],control[None,:])[0]
    np.testing.assert_allclose(predicted,truth,atol=1e-9)
    a,c=kinematic_linearization(state,vehicle.track.reference(state[4])[3])
    assert abs((a@state+c)[0]-truth[3])>.05


def test_frenet_jacobian_matches_finite_difference():
    x = np.array([12.,.3,.4,.12,35.,.8]); k=1/30
    jac, offset = kinematic_linearization(x,k)
    numerical=np.zeros((3,6))
    for i in range(6):
        step=np.zeros(6);step[i]=1e-5
        ap,cp=kinematic_linearization(x+step,k)
        am,cm=kinematic_linearization(x-step,k)
        numerical[:,i]=(ap@(x+step)+cp-am@(x-step)-cm)/2e-5
    np.testing.assert_allclose(jac,numerical,atol=1e-7)


def test_standstill_and_braking_remain_finite():
    vehicle=Vehicle(Track())
    world=vehicle.initial(0)
    for _ in range(50):world=vehicle.step(world,np.array([.4,0.]))
    np.testing.assert_allclose(world,0,atol=.01)
    for _ in range(100):world=vehicle.step(world,np.array([.15,3.]))
    assert world[3]>5 and np.all(np.isfinite(world))
    for _ in range(100):world=vehicle.step(world,np.array([0.,-7.]))
    assert world[3]<.05 and np.all(np.isfinite(world))

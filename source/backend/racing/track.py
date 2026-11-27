"""One geometric definition for Frenet control, projection, and the road mesh.

L-track segments follow urosolia/RacingLMPC (b49c95e), scaled by 20.
"""
from dataclasses import dataclass
import math
import numpy as np
from scipy.spatial import cKDTree


def wrap(angle):
    return (angle + np.pi) % (2 * np.pi) - np.pi


@dataclass
class Segment:
    start: float
    length: float
    curvature: float
    x: float
    y: float
    heading: float


class Track:
    def __init__(self, name="l_track", width=8.0):
        self.name, self.width = name, width
        if name == "l_track":
            r = 90 / math.pi
            specs = [(20, 0), (90, 1/r), (45, -1/r), (90, 1/r), (180/math.pi, 0), (45, 1/r)]
        elif name == "oval":
            specs = [(65, 0), (math.pi*30, 1/30), (130, 0), (math.pi*30, 1/30), (65, 0)]
        else:
            raise ValueError(f"Unknown track: {name}")
        self.segments = []
        s = x = y = heading = 0.0
        for length, curvature in specs:
            self.segments.append(Segment(s, length, curvature, x, y, heading))
            x, y, heading = self._point(self.segments[-1], length)
            s += length
        if math.hypot(x, y) > 1e-6:
            length = math.hypot(x, y)
            closing_heading = math.atan2(-y, -x)
            if abs(wrap(closing_heading-heading)) > 1e-6:
                raise ValueError("Track cannot close with a tangent straight")
            self.segments.append(Segment(s, length, 0, x, y, heading))
            s += length
        self.length = s
        self._starts = np.array([z.start for z in self.segments])
        self._parameters=np.array([[z.start,z.curvature,z.x,z.y,z.heading] for z in self.segments])
        self._grid = np.linspace(0, self.length, math.ceil(self.length/0.4), endpoint=False)
        self._xy = np.array([self.reference(z)[:2] for z in self._grid])
        self._tree = cKDTree(self._xy)

    @staticmethod
    def _point(segment, distance):
        k, h = segment.curvature, segment.heading
        if abs(k) < 1e-12:
            return segment.x+distance*math.cos(h), segment.y+distance*math.sin(h), h
        end = h+k*distance
        return segment.x+(math.sin(end)-math.sin(h))/k, segment.y+(math.cos(h)-math.cos(end))/k, end

    def reference(self, progress):
        s = float(progress) % self.length if hasattr(self, "length") else float(progress)
        i = max(0, int(np.searchsorted(self._starts, s, side="right"))-1)
        segment = self.segments[i]
        x, y, heading = self._point(segment, s-segment.start)
        return x, y, heading, segment.curvature

    def global_pose(self, state):
        x, y, heading, _ = self.reference(state[4])
        return np.array([x-math.sin(heading)*state[5], y+math.cos(heading)*state[5], heading+state[3]])

    def reference_many(self, progress):
        progress=np.asarray(progress,dtype=float)%self.length
        indices=np.maximum(0,np.searchsorted(self._starts,progress,side="right")-1)
        start,k,x,y,h=self._parameters[indices].T
        distance=progress-start;end=h+k*distance
        curved=np.abs(k)>1e-12;safe=np.where(curved,k,1.)
        px=np.where(curved,x+(np.sin(end)-np.sin(h))/safe,x+distance*np.cos(h))
        py=np.where(curved,y+(np.cos(h)-np.cos(end))/safe,y+distance*np.sin(h))
        return np.c_[px,py,end,k]

    def project_many(self, px, py, heading, progress_guess):
        """Local Newton projection, retaining unwrapped progress across the line."""
        s=np.array(progress_guess,dtype=float,copy=True)
        for _ in range(6):
            x,y,tangent,k=self.reference_many(s).T
            dx,dy=px-x,py-y
            ey=-dx*np.sin(tangent)+dy*np.cos(tangent)
            s+=(dx*np.cos(tangent)+dy*np.sin(tangent))/(1-k*ey)
        x,y,tangent,_=self.reference_many(s).T
        ey=-(px-x)*np.sin(tangent)+(py-y)*np.cos(tangent)
        return np.c_[wrap(heading-tangent),s,ey]

    def project(self, px, py, heading, previous_s=None):
        _, i = self._tree.query([px, py])
        s = float(self._grid[i])
        if previous_s is not None:
            s += round((previous_s-s)/self.length)*self.length
        result=self.project_many(np.array([px]),np.array([py]),np.array([heading]),np.array([s]))[0]
        if previous_s is None:result[1]%=self.length
        return result

    def samples(self, spacing=1.0):
        result = []
        for s in np.linspace(0, self.length, math.ceil(self.length/spacing)+1):
            x, y, heading, curvature = self.reference(s)
            result.append({"s": float(s), "x": x, "y": y, "heading": heading, "curvature": curvature})
        return result

    def manifest(self):
        return {"name": self.name, "width": self.width, "length": self.length, "samples": self.samples()}


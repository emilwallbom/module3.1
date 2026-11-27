using UnityEngine;

namespace CorvetteLab
{
    // Presentation-side keyboard mapping only. Never used by the autonomous controller.
    public static class KeyboardSteering
    {
        public static float Limit(float speed)
        {
            float ratio=Mathf.Abs(speed)/12f;
            return Mathf.Clamp(.45f/(1+ratio*ratio),.085f,.45f);
        }
        public static float Step(float current,float direction,float speed,float dt)
        {
            float target=Mathf.Clamp(direction,-1,1)*Limit(speed);
            float rate=direction==0?8f:(current*direction<0?6f:4f);
            return Mathf.MoveTowards(current,target,rate*Mathf.Max(0,dt));
        }
    }
}

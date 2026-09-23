import math
def l93_to_wgs(x,y):
    a=6378137.0; f=1/298.257222101; e=math.sqrt(2*f-f*f)
    p1,p2,p0=map(math.radians,(44,49,46.5)); l0=math.radians(3)
    def m(p): return math.cos(p)/math.sqrt(1-(e*math.sin(p))**2)
    def t(p): return math.tan(math.pi/4-p/2)/((1-e*math.sin(p))/(1+e*math.sin(p)))**(e/2)
    n=(math.log(m(p1))-math.log(m(p2)))/(math.log(t(p1))-math.log(t(p2)))
    F=m(p1)/(n*t(p1)**n); r0=a*F*t(p0)**n
    dx=x-700000; dy=r0-(y-6600000)
    r=math.copysign(math.hypot(dx,dy),n); th=math.atan2(dx,dy)
    tt=(r/(a*F))**(1/n); lat=math.pi/2-2*math.atan(tt)
    for _ in range(10):
        lat=math.pi/2-2*math.atan(tt*((1-e*math.sin(lat))/(1+e*math.sin(lat)))**(e/2))
    return math.degrees(lat), math.degrees(th/n+l0)
if __name__=="__main__":
    print(l93_to_wgs(463020.3915885668,6455676.271976542))

from sympy import *

m0x, m0y, m1x, m1y, m2x, m2y, rr, wr, dx, dy, dt = symbols('m0x, m0y, m1x, m1y, m2x, m2y, rr, wr, dx, dy, dt')
w1, w2, w3 = symbols('w1, w2, w3')

eq1 = Eq(w1, (m0x*dx + m0y*dy + rr*dt)/(wr))
eq2 = Eq(w2, (m1x*dx + m1y*dy + rr*dt)/(wr))
eq3 = Eq(w3, (m2x*dx + m2y*dy + rr*dt)/(wr))

r = solve((eq1, eq2, eq3), (dx, dy, dt))

print(r[dx].simplify())
print(r[dy].simplify())
print(r[dt].simplify())


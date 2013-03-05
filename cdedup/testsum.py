import rollingcs
from time import time


#rollingcs.benchmark()
#rollingcs.test()

one_mb_data = "x" * (2**20)
one_hundred_mb_data = "x" * (2**20 * 100)

t0 = time()
for i in range(0, 100):
    rollingcs.calc_rolling(one_mb_data, len(one_mb_data))
print "rollingcs.calc_rolling(): 100 mb with 1 mb per call: ", time() - t0

t0 = time()
rollingcs.calc_rolling(one_hundred_mb_data, len(one_hundred_mb_data))
print "rollingcs.calc_rolling(): 100 mb with 100 mb per call: ", time() - t0

rs = rollingcs.RollingChecksum(1023, rollingcs.IntegerSet(1))
t0 = time()
rs.feed_string(one_hundred_mb_data)
rs.value()
print "rollingcs.RollingChecksum.feed_string(): 100 mb with 100 mb per call: ", time() - t0

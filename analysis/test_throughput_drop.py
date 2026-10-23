import unittest
import numpy as np
from throughput_drop import CounterSeries,Pass,reference_rate,phase_label
class WindowTests(unittest.TestCase):
 def test_weights_partial_intervals_by_time(self):
  s=CounterSeries([0,3,6,9],[np.nan,10,20,40])
  self.assertAlmostEqual(s.integral(1,8),2*10+3*20+2*40)
  self.assertAlmostEqual(s.coverage(1,8),7)
 def test_long_gaps_are_missing_not_zero(self):
  s=CounterSeries([0,3,12,15],[np.nan,10,0,20],6)
  self.assertAlmostEqual(s.coverage(0,15),6)
  self.assertAlmostEqual(s.integral(0,15),90)
 def test_zero_is_a_valid_measured_rate(self):
  s=CounterSeries([0,3,6],[np.nan,0,0]);self.assertEqual(s.integral(0,6),0);self.assertEqual(s.coverage(0,6),6)
 def test_pass_guard_and_crossing(self):
  p=Pass(1,0,100,100,1,1)
  self.assertTrue(p.contains(6,94,6));self.assertFalse(p.contains(5,35,6));self.assertFalse(p.contains(75,105,6))
 def test_reference_uses_trial_equal_weight_and_requires_support(self):
  refs=[{h:{1:(np.array([.49,.5,.51]),np.array([v,v,v]))} for h in ['node12','node13']} for v in [10,20,30]]
  r=reference_rate(refs,[1,1],[.5,.5],.01);self.assertEqual(r[0],40)
  self.assertIsNone(reference_rate(refs,[1,1],[.9,.5],.01))
 def test_phase_crossing_is_labeled(self):
  e={'down':0,'marked_out':600,'recovering':606,'healthy':1000}
  self.assertEqual(phase_label(590,620,e),'grace+remapping+active_repair')
if __name__=='__main__':unittest.main()

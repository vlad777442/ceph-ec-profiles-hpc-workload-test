import unittest
from kernel_guard import has_failure
class KernelErrorDetection(unittest.TestCase):
 def test_known_failure_chain(self):
  for line in ['page allocation failure: order:5','rbd: rbd2: copyup failed: -12','rbd: rbd2: write at objno 8939 0~2912256 result -12','Buffer I/O error on device rbd2','EXT4-fs warning (device rbd2): I/O error 9','blk_update_request: kernel resource error, dev rbd2']:
   with self.subTest(line=line):self.assertTrue(has_failure(line))
 def test_normal_messages(self):
  for line in ['rbd: rbd2: capacity 1234803097600 features 0x1','EXT4-fs (rbd2): mounted filesystem with ordered data mode','ceph: client session established']:
   with self.subTest(line=line):self.assertFalse(has_failure(line))
if __name__=='__main__':unittest.main()

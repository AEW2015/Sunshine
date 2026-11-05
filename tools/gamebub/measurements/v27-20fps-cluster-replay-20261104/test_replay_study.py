"""@brief Regression checks for the artifact-only transport replay study."""
import unittest
import os
from replay_study import export_schedule, datagrams, inspect_schedule, replay
from reference_loopback import load_reference
from replay_study import HERE


class ReplayTests(unittest.TestCase):
    """@brief Verify replay retains boundaries and distinguishes injected corruption."""
    @classmethod
    def setUpClass(cls):
        """@brief Load the same hash-checked transport reference as the study."""
        cls.reference = load_reference(os.environ.get('MOONBUB_REFERENCE',HERE/'artifacts/moonbub-30fps-study'))

    def schedule(self):
        """@brief Return two synthetic frames with tails and a neighboring SOF."""
        return [dict(frame_id=fid,capture_us=fid,jpeg_bytes=2048,offset=offset,
            count=1024,post_send_s=stamp,flags=flag)
            for fid,offset,stamp,flag in ((7,0,1.0,1),(7,1024,1.003,2),
                (8,0,1.006,1),(8,1024,1.009,2))]

    def test_crc_and_complete_frames(self):
        """@brief New synthetic CRCs allow complete reference ingress."""
        result=replay(self.reference,self.schedule())
        self.assertEqual(result,{'completed_ids':[7,8],'errors':[]})
        self.assertEqual(len(list(datagrams(self.schedule()))[0]),1064)

    def test_export_keeps_original_order_and_frame_tails(self):
        """@brief Export only the selected frame with the logged frame length."""
        rows=[{'event':'ignored'},{'event':'send','frame_id':7,'jpeg_bytes':2048},
            {'event':'packet_timing','frame_id':6,'capture_us':6,'packets':[]},
            {'event':'packet_timing','frame_id':7,'capture_us':7,
             'packets':[[0,1024,1.0],[1024,1024,1.003]]}]
        self.assertEqual(export_schedule(rows,7,7),self.schedule()[:2])

    def test_boundaries_and_timestamp_regression(self):
        """@brief Do not hide malformed order by sorting the source."""
        schedule=self.schedule()
        result=inspect_schedule(schedule)
        self.assertEqual(result['order_errors'],[])
        self.assertAlmostEqual(result['frame_boundaries'][0]['tail_to_sof_gap_ms'],3)
        schedule[2]['post_send_s']=0.9
        self.assertIn('timestamp moved backward',str(inspect_schedule(schedule)))

    def test_missing_tail_and_prefix_are_identified(self):
        """@brief Dropped old tail and new SOF create an identity conflict, not proof of reorder."""
        schedule=self.schedule()
        result=replay(self.reference,[schedule[0],schedule[3]])
        self.assertEqual(result['completed_ids'],[])
        self.assertEqual(result['errors'][0]['reason'],'no matching frame start')
        self.assertIn('previous frame incomplete',str(inspect_schedule([schedule[0],schedule[3]])))
        self.assertIn('offset discontinuity',str(inspect_schedule([schedule[0],schedule[3]])))

    def test_within_frame_reordering_fails_and_new_sof_recovers(self):
        """@brief A reordered frame is distinguishable from subsequent valid recovery."""
        schedule=self.schedule()
        result=replay(self.reference,[schedule[1],schedule[0],*schedule[2:]])
        self.assertTrue(result['errors'])
        self.assertEqual(result['completed_ids'],[8])


if __name__=='__main__':
    unittest.main()

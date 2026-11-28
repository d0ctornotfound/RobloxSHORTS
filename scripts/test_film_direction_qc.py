"""Contract regressions for flow gates. Run with plain Python, no Blender."""
from film_qc import flow_report

def rows(n=30, principal_moving=True, background_moving=True, face_height=.45):
    return [{"frame":i,"actor_qc":{"principal":{"face_all":{"visible_fraction":1,"samples":49},"face_external":{"blocked":0}}},"direction":{"beat_type":"emotion","principal":"principal","listeners":[],"camera_move":"push","grade":{"preset":"warm_saturated_v1"},"actors":{
        "principal":{"pose":[[i*.002 if principal_moving else 0,0,0]],"face_facing_dot":.9,"face_height":face_height,"face_safe":True},
        "background":{"pose":[[0,i*.002 if background_moving else 0,0]],"face_height":.10,"face_safe":True}
    }}} for i in range(n)]

def main():
    assert flow_report(rows(),expected_frames=30)["status"]=="numeric_pass"
    held=flow_report(rows(background_moving=False),expected_frames=30)
    assert held["status"]=="flag" and not held["checks"]["all_actor_holds"]
    camera_only=flow_report(rows(principal_moving=False),expected_frames=30)
    assert camera_only["status"]=="flag" and camera_only["actors"]["principal"]["motion_coverage"]==0
    assert camera_only["actors"]["principal"]["held_pose_max_s"]==1
    scale=flow_report(rows(face_height=.399),expected_frames=30)
    assert scale["status"]=="flag" and not scale["checks"]["face_scale"]
    edge=rows();edge[0]["direction"]["actors"]["principal"]["face_facing_dot"]=.01
    assert not flow_report(edge)["checks"]["readable_faces"]
    assert flow_report(rows()[:-1],expected_frames=30)["status"]=="unmeasured"
    gap=rows();gap.pop(10);assert flow_report(gap)["status"]=="unmeasured"
    assert flow_report([{"frame":0}],expected_frames=1)["status"]=="unmeasured"
    print("flow contract tests passed")
if __name__=="__main__":main()

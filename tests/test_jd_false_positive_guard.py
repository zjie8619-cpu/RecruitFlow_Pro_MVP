from backend.services.jd_ai import generate_jd_bundle

def _concat(bundle):
    return (bundle.get("jd_long","") or "") + (bundle.get("jd_short","") or "") + \
           " ".join(d.get("name","") for d in bundle.get("dimensions",[]))

def test_frontend_jd_should_not_contain_competition_terms():
    jd = generate_jd_bundle(
        job_title="前端开发工程师",
        must="熟悉 JavaScript / Vue / React",
        nice="有教育行业经验更佳",
        exclude="不接受纯实习"
    )
    full_text = _concat(jd)
    for kw in ["竞赛", "LaTeX", "国一", "奥赛", "刷题", "带队", "教案", "赛题"]:
        assert kw not in full_text
    dims = jd["dimensions"]
    assert len(dims) == 5
    assert abs(sum(d["weight"] for d in dims) - 1.0) < 1e-6
    for dim in dims:
        anchors = dim.get("anchors") or {}
        assert {"20", "60", "100"}.issubset(set(anchors.keys()))
        assert all(isinstance(anchors[k], str) and anchors[k] for k in ["20", "60", "100"])

def test_math_competition_coach_can_contain_competition_terms():
    jd = generate_jd_bundle(
        job_title="数学竞赛教练",
        must="有带队参加竞赛获奖经验",
        nice="熟悉 LaTeX 排版",
        exclude=""
    )
    full_text = _concat(jd)
    assert any(kw in full_text for kw in ["竞赛", "LaTeX", "带队"])



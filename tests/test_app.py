from pathlib import Path
import httpx

from edutech.speech_eval import DialogOption, evaluate_spoken_response


def test_speech_evaluation_logic() -> None:
    options = [
        DialogOption(id="A", text="I'm reading a business news summary.", is_correct=True),
        DialogOption(id="B", text="Yes, the stock price has increased a lot.", is_correct=False),
        DialogOption(id="C", text="I agree with you that it's disgusting.", is_correct=False),
    ]

    # 1. Exact / fluent match on Option A (with expanded contraction "I am")
    res_correct = evaluate_spoken_response("I am reading a business news summary", options)
    assert res_correct.matched_option_id == "A"
    assert res_correct.is_correct_option is True
    assert res_correct.passed is True
    assert res_correct.pronunciation_score >= 90.0

    # 2. Wrong option spoken (Option B)
    res_wrong = evaluate_spoken_response("Yes the stock price has increased a lot", options)
    assert res_wrong.matched_option_id == "B"
    assert res_wrong.is_correct_option is False
    assert res_wrong.passed is False

    # 3. Partial / incomplete pronunciation of Option A
    res_partial = evaluate_spoken_response("I'm reading a", options)
    assert res_partial.matched_option_id == "A"
    assert res_partial.is_correct_option is True
    assert res_partial.passed is False
    assert any(w.status == "missing" for w in res_partial.word_feedback)


def test_live_server_endpoints() -> None:
    base_url = "http://127.0.0.1:8085"
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        # 1. Index HTML
        r_index = client.get("/")
        assert r_index.status_code == 200
        assert "Self-Study Lesson View" in r_index.text

        # 2. Lesson config & generated Veo videos
        r_lesson = client.get("/api/lesson")
        assert r_lesson.status_code == 200
        lesson = r_lesson.json()
        assert len(lesson["available_videos"]) >= 4
        assert len(lesson["checkpoints"]) == 2

        # 3. Verify static video file serving with HTTP Range support
        video_url = lesson["default_video_url"]
        r_video = client.get(video_url, headers={"Range": "bytes=0-1023"})
        assert r_video.status_code in (200, 206)
        assert len(r_video.content) > 0

        # 4. Evaluate speech endpoint for Checkpoint 1 & Checkpoint 2
        r_eval1 = client.post(
            "/api/evaluate-speech",
            json={"transcript": "I'm reading a business news summary.", "checkpoint_id": 1},
        )
        assert r_eval1.status_code == 200
        data1 = r_eval1.json()
        assert data1["passed"] is True
        assert data1["matched_option_id"] == "A"

        r_eval2 = client.post(
            "/api/evaluate-speech",
            json={"transcript": "Yes, the stock price has increased a lot.", "checkpoint_id": 2},
        )
        assert r_eval2.status_code == 200
        data2 = r_eval2.json()
        assert data2["passed"] is True
        assert data2["matched_option_id"] == "B"


if __name__ == "__main__":
    test_speech_evaluation_logic()
    test_live_server_endpoints()
    print("ALL TESTS PASSED SUCCESSFULLY!")

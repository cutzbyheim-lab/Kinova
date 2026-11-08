"""Real Remotion render of a short cut. Slow (~1 min); runs when TEST_MOTION=true and Node + the bundle exist."""

import os
import subprocess

import pytest

from app.media.ffmpeg import probe
from app.media.motion import available
from app.media.plan import Variation
from app.media.qc import check_output
from app.media.render import Source, render_variation

pytestmark = pytest.mark.skipif(os.environ.get("TEST_MOTION") != "true" or not available()[0],
                                reason="motion layer not enabled for this run")


def test_motion_render_end_to_end(tmp_path):
    src = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=8",
                    "-f", "lavfi", "-i", "sine=frequency=300:duration=8", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", "-shortest", str(src)], check=True)
    var = Variation(key="hook", hook_text="Watch this one", cta_text="",
                    clips=[{"start": 0, "end": 3, "focus_x": 0.3}, {"start": 4, "end": 7, "zoom": 1.15}])
    words = {"segments": [{"start": 0.5, "end": 2.5, "text": "x", "words": [
        {"start": 0.5, "end": 0.9, "word": "this"}, {"start": 1.0, "end": 1.4, "word": "is"},
        {"start": 1.5, "end": 2.2, "word": "great."}]}]}
    r = render_variation([Source(src, probe(src))], var, words, tmp_path / "out")
    assert r.motion_used, r.motion_error
    q = check_output(r.video, 1080, 1920, r.duration, False, 0)
    assert q["passed"], q

# S03: Doctor integration, docs, verify-m004.sh, milestone closure — UAT

**Milestone:** M004
**Written:** 2026-04-07T18:37:00.339Z

## UAT — M004/S03: Closure (doctor + docs + verify + R024)

### Verify the closure signal

```bash
bash scripts/verify-m004.sh --skip-integration
# Expected: 9 steps, 0 failed, "M004 VERIFICATION PASSED"
```

### Verify the doctor row

```bash
vidscope doctor
# Expected output includes a row:
#   analyzer | ok | heuristic (default, zero cost)
```

### Verify each provider produces an Analysis (no real keys needed)

```bash
python -m uv run python -c "
import httpx, json
from vidscope.adapters.llm.groq import GroqAnalyzer
from vidscope.domain import Language, Transcript, TranscriptSegment, VideoId

def handler(req):
    return httpx.Response(200, json={
        'choices': [{'message': {'role': 'assistant', 'content': json.dumps({
            'language': 'en', 'keywords': ['demo'], 'topics': ['test'], 'score': 50, 'summary': 'demo'
        })}}]
    })

client = httpx.Client(transport=httpx.MockTransport(handler))
analyzer = GroqAnalyzer(api_key='fake', client=client)
t = Transcript(video_id=VideoId(1), language=Language.ENGLISH, full_text='demo', segments=())
print(analyzer.analyze(t))
"
# Expected: Analysis(provider='groq', score=50.0, ...)
```

### Verify R024 is validated

```bash
grep -A 2 "^### R024" .gsd/REQUIREMENTS.md
# Expected: status: validated
```

### Verify docs

```bash
test -f docs/analyzers.md && echo "OK"
# Expected: OK
```

### Quality gates

- [x] ruff clean
- [x] mypy strict 81 source files
- [x] pytest 558 passed
- [x] lint-imports 9 contracts kept
- [x] verify-m004.sh 9/9 steps green


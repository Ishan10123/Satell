"""Print bounded aggregate RAG operational metrics without message content."""

from collections import Counter, defaultdict
import json
import math

from django.core.management.base import BaseCommand, CommandError

from conversations.models import GenerationMetadata


class Command(BaseCommand):
    help = "Show bounded aggregate request outcomes and stage latency percentiles."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=500)

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 10_000:
            raise CommandError("--limit must be between 1 and 10000.")
        records = list(GenerationMetadata.objects.order_by("-created_at").values(
            "verification_status", "stage_timings", "diagnostics"
        )[:limit])
        statuses = Counter(record["verification_status"] for record in records)
        errors = Counter()
        timings = defaultdict(list)
        for record in records:
            diagnostics = record["diagnostics"] if isinstance(record["diagnostics"], dict) else {}
            if diagnostics.get("failure_code"):
                errors[str(diagnostics["failure_code"])] += 1
            stage_values = record["stage_timings"] if isinstance(record["stage_timings"], dict) else {}
            for stage, value in stage_values.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 10_000_000:
                    timings[str(stage)].append(float(value))
        result = {
            "sample_size": len(records),
            "request_outcomes": dict(sorted(statuses.items())),
            "failed_request_count": statuses.get("failed", 0),
            "safe_abstention_count": statuses.get("abstained", 0),
            "error_categories": dict(sorted(errors.items())),
            "stage_latency_ms": {stage: self._percentiles(values)
                                  for stage, values in sorted(timings.items())},
        }
        self.stdout.write(json.dumps(result, indent=2, sort_keys=True))

    @staticmethod
    def _percentiles(values):
        values = sorted(values)
        def at(p):
            if len(values) == 1:
                return round(values[0], 3)
            index = (len(values) - 1) * p
            lower = math.floor(index)
            upper = math.ceil(index)
            return round(values[lower] + (values[upper] - values[lower]) * (index - lower), 3)
        return {"count": len(values), "minimum": round(values[0], 3), "p50": at(.5),
                "p95": at(.95), "maximum": round(values[-1], 3)}

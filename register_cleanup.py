"""Register the daily cleanup callback with Infrai."""

import os

import infrai


def register_cleanup() -> str:
    task_url = os.environ["SWEEP_TASK_URL"]
    result = infrai.cron.create(cron_expr="15 2 * * *", task=task_url)
    return str(result["job_id"])


if __name__ == "__main__":
    print(f"registered cleanup job: {register_cleanup()}")

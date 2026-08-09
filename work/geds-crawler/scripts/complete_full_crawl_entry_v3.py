"""Scheduler entrypoint using PowerShell Task Scheduler rescheduling."""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta

import complete_full_crawl as completion


original_read_state = completion.read_state


def read_state_without_terminal_error_loop():
    state = original_read_state()
    if state["run"][0] != "running":
        state["queue"].pop("error", None)
    return state


def reschedule_with_task_api():
    run_at = (datetime.now() + timedelta(hours=1)).isoformat(timespec="seconds")
    wrapper = str(completion.ROOT / "tools" / "run-geds-crawl-completion-v3.ps1")
    command = (
        "$taskName='GEDS-Full-Crawl-Completion'; "
        f"$runAt=[datetime]::Parse('{run_at}'); "
        f"$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -ExecutionPolicy Bypass -File \"{wrapper}\"'; "
        "$trigger=New-ScheduledTaskTrigger -Once -At $runAt; "
        "$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries; "
        "$principal=New-ScheduledTaskPrincipal -UserId \"$env:USERDOMAIN\\$env:USERNAME\" -LogonType Interactive -RunLevel Limited; "
        "Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null; "
        "Write-Output ('rescheduled=' + (Get-ScheduledTaskInfo -TaskName $taskName).NextRunTime.ToString('o'))"
    )
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", command], check=True)


completion.read_state = read_state_without_terminal_error_loop
completion.reschedule = reschedule_with_task_api
raise SystemExit(completion.main())

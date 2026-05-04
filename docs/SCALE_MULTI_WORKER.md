# Scale Multi-Worker Plan

Workers report machine name, OS, capabilities, mode and current job. The queue monitor summarizes queued/running/retryable/failed/dead-letter jobs.

Next steps:

- add pause/resume worker API
- persist retry policies
- store dead-letter job records
- add worker success/failure rate
- assign provider/key/budget by worker

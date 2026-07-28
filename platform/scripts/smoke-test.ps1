param(
    [string]$ApiBase = "http://localhost:8000",
    [int]$TimeoutSeconds = 45
)

$ErrorActionPreference = "Stop"

function Assert-Condition([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "Smoke test failed: $Message" }
}

Write-Host "Checking API health..."
$health = Invoke-RestMethod "$ApiBase/health"
Assert-Condition ($health.status -eq "ok") "API is not healthy."

$suffix = [guid]::NewGuid().ToString("N").Substring(0, 10)
$signup = @{
    # Pydantic's email validator rejects reserved domains such as .test.
    # This account is local-only; no email is sent.
    email = "smoke-$suffix@gmail.com"
    password = "SmokeTest-12345"
    display_name = "Compose smoke test"
} | ConvertTo-Json

Write-Host "Creating isolated smoke-test account..."
$session = Invoke-RestMethod -Method Post -Uri "$ApiBase/auth/signup" -ContentType "application/json" -Body $signup
$headers = @{ Authorization = "Bearer $($session.access_token)" }

$project = Invoke-RestMethod -Method Post -Uri "$ApiBase/projects" -Headers $headers -ContentType "application/json" -Body (@{ name = "Smoke project $suffix" } | ConvertTo-Json)
Assert-Condition ($null -ne $project.id) "Project was not created."

Write-Host "Submitting mock research..."
$run = Invoke-RestMethod -Method Post -Uri "$ApiBase/research" -Headers $headers -ContentType "application/json" -Body (@{
    project_id = $project.id
    question = "Does the Compose smoke-test worker produce an auditable report?"
} | ConvertTo-Json)
Assert-Condition ($null -ne $run.id) "Research run was not created."

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$job = $null
do {
    Start-Sleep -Milliseconds 750
    $job = (Invoke-RestMethod "$ApiBase/jobs" -Headers $headers | Where-Object { $_.research_run_id -eq $run.id } | Select-Object -First 1)
    if ($job -and $job.status -in @("succeeded", "failed", "cancelled")) { break }
} while ((Get-Date) -lt $deadline)

Assert-Condition ($null -ne $job) "Scheduler did not create a job."
Assert-Condition ($job.status -eq "succeeded") "Job ended as '$($job.status)': $($job.error)"

$events = Invoke-RestMethod "$ApiBase/jobs/$($job.id)/events" -Headers $headers
Assert-Condition (($events.status -contains "assigned") -and ($events.status -contains "running") -and ($events.status -contains "succeeded")) "Expected job lifecycle events are missing."

$report = Invoke-RestMethod "$ApiBase/reports" -Headers $headers | Where-Object { $_.research_run_id -eq $run.id } | Select-Object -First 1
Assert-Condition ($null -ne $report) "Report metadata was not created."
Assert-Condition ($null -ne $report.markdown_artifact_id) "Markdown artifact reference is missing."

$markdown = Invoke-WebRequest "$ApiBase/artifacts/$($report.markdown_artifact_id)/content" -Headers $headers -UseBasicParsing
Assert-Condition ($markdown.Content -match "Research run") "Stored report content is invalid."

Write-Host "PASS: signup -> project -> research -> worker -> MinIO report -> authenticated retrieval"

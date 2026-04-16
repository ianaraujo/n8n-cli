# n8n CLI — command examples

Concrete CLI invocations. All commands print JSON to stdout.

## Discover

```bash
# List active workflows
n8n list --active

# Find a workflow without knowing its ID
n8n list | jq '.[] | select(.name | test("invoice"; "i"))'
```

## Understand

```bash
# Graph view (cheapest) — nodes, types, edges
n8n flow --name "Invoice Processing"

# Full JSON of a single node
n8n get --name "Invoice Processing" --node "HTTP Request"

# Full workflow, compact (no position/id noise)
n8n get --name "Invoice Processing" --compact
```

## Debug

```bash
# Last 5 failed runs
n8n executions --name "Daily Report" --status error --limit 5

# Which node failed and why
n8n execution-data 987

# Full input/output for a specific node in that run
n8n execution-data 987 --node "Send Email"
```

## Patch a single parameter

```bash
# String value — preview then apply
n8n set-node-param --name "Order Sync" --node "Fetch Orders" \
  --param "url" --value "https://api.example.com/v2/orders" --dry-run

n8n set-node-param --name "Order Sync" --node "Fetch Orders" \
  --param "url" --value "https://api.example.com/v2/orders"

# Non-string value (number, object, array, boolean) — use --json
n8n set-node-param --name "Order Sync" --node "Batch" \
  --param "options.batchSize" --json 50

n8n set-node-param --name "Order Sync" --node "HTTP Request" \
  --param "queryParameters.parameters" \
  --json '[{"name":"status","value":"open"}]'
```

## Full-workflow round-trip

```bash
# Export with credentials preserved (required for round-trip)
n8n get --name "Customer Onboarding" --keep-creds -o /tmp/wf.json

# Edit /tmp/wf.json by hand or with jq...
jq '.nodes |= map(if .name == "Slack" then .parameters.text = "Error: {{ $json.error }}" else . end)' \
  /tmp/wf.json > /tmp/wf.new.json

# Preview structural diff, then apply
n8n update-workflow --name "Customer Onboarding" --file /tmp/wf.new.json --dry-run
n8n update-workflow --name "Customer Onboarding" --file /tmp/wf.new.json
```

## Retry

```bash
# Retry with the current (fixed) workflow
n8n retry 987 --use-latest

# Retry with the workflow as it was when 987 originally ran
n8n retry 987
```

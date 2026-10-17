@platform
Feature: The stacks report their own telemetry when the overlay is on
  As the operator watching a run
  I want each stack's requests, database work and booking outcomes on the dashboard
  So that I can see what a retry did without reading the database

  # Traces to: platform plan section 3.3 and section 5, step 5. The plan starts
  # with python; the author asked for all three stacks in step 5 (rule G8).
  # Needs the cluster from make up, the stacks from make deploy and the overlay
  # from make observe-up.

  @rule-G0
  Scenario Outline: A keyed booking leaves one trace with its database work
    Given the observability overlay is on for the <stack> stack
    When a client books a session with an idempotency key on the <stack> stack
    Then one trace shows the HTTP request span
    And the trace shows the database spans inside it

    Examples:
      | stack  |
      | python |
      | java   |
      | dotnet |

  @rule-G2
  Scenario Outline: The dashboard counts a replayed booking as a replay
    Given the observability overlay is on for the <stack> stack
    When a client sends the same keyed booking twice on the <stack> stack
    Then the outcome counter shows one more created booking
    And the outcome counter shows one more replayed booking

    Examples:
      | stack  |
      | python |
      | java   |
      | dotnet |

  @spec-run-matrix
  Scenario: The dashboard shows which stack is under test
    Given the observability overlay is on
    When the matrix scales python to 0 replicas
    Then the ready replicas panel shows python at 0

  @contract-8
  Scenario Outline: Telemetry is off unless the overlay switches it on
    Given the <stack> Deployment from infra/k8s/<stack>.yaml
    When the contract tests run against the <stack> stack
    Then every contract test passes
    And the <stack> pod exports no telemetry

    Examples:
      | stack  |
      | python |
      | java   |
      | dotnet |

@platform
Feature: The booking namespace admits only its permitted connections
  As the operator hardening the cluster
  I want the default-deny policy to gate every pod
  So that only the planned arrows carry traffic

  # Traces to: the spec's Infrastructure section and platform plan section 5, step 3.

  @spec-infrastructure
  Scenario Outline: Only permitted connections reach the booking database
    Given default-deny NetworkPolicy is applied in wcf-physics
    When <client> opens a connection to postgres on port 5432
    Then the connection is <result>

    Examples:
      | client        | result   |
      | python        | accepted |
      | schema-job    | accepted |
      | otel-agent    | refused  |

  @contract-2
  Scenario: The host still reaches the python stack through its NodePort
    Given default-deny NetworkPolicy is applied in wcf-physics
    When the contract tests run against the python stack
    Then every contract test passes

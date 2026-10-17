@exp3 @health @contract-1 @spec-exp3-L71
Feature: The health check names the stack that answers
  As the operator running the matrix
  I want each service to say which stack it is
  So that load is never sent to the wrong stack

  # Traces to: docs/exp3-spec.md line 71 and contract test 1.

  @happy
  Scenario: The health check reports ok and the stack's name
    Given the booking service for the stack under test is running
    When the operator checks the service's health
    Then the service reports it is ok and names the stack under test

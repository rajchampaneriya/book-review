@exp3 @control @spec-exp3-L73-79
Feature: The naive booking baseline books every attempt, by design
  As the experimenter
  I want the control group to create a booking and a charge for every attempt
  So that duplicates under retry can be measured against the keyed endpoint

  # Traces to: docs/exp3-spec.md lines 73-79, .claude/rules/naive-baseline.md, contract test 2.
  # A result of "two bookings" here is the expected behaviour, not a bug. Do not "fix" it.

  Background:
    Given the booking service for the stack under test is running

  @contract-2 @happy
  Scenario: A repeated naive booking creates a second booking and a second charge
    Given the client has booked session "s-42" on the naive endpoint
    When the client sends the identical naive booking again
    Then the client receives a different booking confirmation
    And two bookings and two deposit charges exist for that client reference

  @fault-injection @spec-exp3-L108-119
  Scenario: A confirmation lost after commit double-charges on the naive endpoint
    Given fault injection is enabled on the stack under test
    And the client's first attempt will lose its confirmation after the booking commits
    When the client books on the naive endpoint and retries after the timeout
    Then two bookings and two deposit charges exist for that client reference

  @happy
  Scenario: The naive endpoint ignores a request key
    When the client books on the naive endpoint with a fresh request key
    Then the client receives a new booking confirmation
    And no request key is stored

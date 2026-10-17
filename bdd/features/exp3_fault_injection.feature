@exp3 @fault-hook @spec-exp3-L108-119
Feature: The fault hook delays a committed confirmation only when injection is enabled
  As the experimenter
  I want to lose the confirmation of an already committed booking on demand
  So that the client's retry meets a booking that already exists

  # Traces to: docs/exp3-spec.md lines 108-119 and contract test 8.
  # Timing scenarios start from a warmed-up service so a cold JIT or a fresh pod
  # cannot fail them (see BDD_REVIEW.md, finding B2).

  Background:
    Given the booking service for the stack under test has served a warm-up booking

  @contract-8 @happy
  Scenario: The fault header is ignored while injection is disabled
    Given fault injection is disabled on the stack under test
    When the client books with the hold-after-commit fault header
    Then the confirmation arrives in under 500 ms
    And exactly one booking exists for that request

  @fault-injection @happy
  Scenario: The fault header holds the confirmation after the booking commits
    Given fault injection is enabled with a 2000 ms hold
    When the client books with the hold-after-commit fault header
    Then the booking is recorded before the confirmation arrives
    And the confirmation arrives no sooner than 2000 ms after the request

  @fault-injection @edge
  Scenario: An unrecognised fault header value is ignored
    Given fault injection is enabled with a 2000 ms hold
    When the client books with the fault header value "something-else"
    Then the confirmation arrives in under 500 ms

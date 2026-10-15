@exp3 @treatment @spec-exp3-L81-106
Feature: A retried booking with the same request key is never booked or charged twice
  As a client whose confirmation can be lost on the way back
  I want a retry that carries the same request key to return the original confirmation
  So that a dog owner is booked and charged exactly once

  # Traces to: docs/exp3-spec.md lines 81-106 (POST /v2/bookings) and contract tests 3-6.
  # Level: HTTP contract, run against the stack named by STACK (make contract).
  # Every scenario creates its own request key and client reference, so scenarios
  # never depend on each other or on a truncated schema.

  Background:
    Given the booking service for the stack under test is running

  @contract-4 @happy
  Scenario: A first booking with a fresh request key is confirmed once
    Given a fresh request key
    When the client books session "s-42" for dog "d-7" with a 2500-cent deposit
    Then the client receives a new booking confirmation
    And exactly one booking and one 2500-cent deposit charge exist for that request

  @contract-4 @happy
  Scenario: Retrying with the same request key replays the original confirmation
    Given the client has booked session "s-42" with a fresh request key
    When the client retries the identical booking with the same request key
    Then the client receives the original confirmation marked as a replay
    And exactly one booking and one deposit charge exist for that request

  @fault-injection @spec-exp3-L108-119
  Scenario: A confirmation lost after the booking commits does not double-book the retry
    Given fault injection is enabled on the stack under test
    And the client's first attempt will lose its confirmation after the booking commits
    When the client books with a fresh request key and retries after the timeout
    Then the client receives a confirmation marked as a replay
    And exactly one booking and one deposit charge exist for that request

  @contract-5 @failure
  Scenario Outline: Reusing a request key for a different booking is refused as a conflict
    Given the client has booked session "s-42" with a fresh request key
    When the client books again with the same request key but a different <detail>
    Then the booking is refused as a request-key conflict
    And still exactly one booking and one deposit charge exist for that request key

    Examples:
      | detail           |
      | client reference |
      | session          |
      | dog              |
      | owner            |
      | deposit amount   |

  @contract-6 @edge
  Scenario: Twenty simultaneous duplicates produce exactly one booking
    When 20 identical bookings with the same fresh request key arrive at the same time
    Then all 20 clients receive the same booking confirmation
    And exactly one of those confirmations is not marked as a replay
    And exactly one booking and one deposit charge exist for that request

  @contract-3 @failure @spec-exp3-L83-84
  Scenario Outline: A booking without a usable request key is refused
    When the client books with <key>
    Then the booking is refused because a request key is required
    And no booking or charge is recorded for that client reference

    Examples:
      | key                                     |
      | no request key                          |
      | an empty request key                    |
      | a 256-character request key             |
      | a request key containing a space        |
      | a request key containing a non-ASCII letter |

  @edge @spec-exp3-L83
  Scenario: The longest permitted request key is accepted
    When the client books with a 255-character request key
    Then the client receives a new booking confirmation
    And exactly one booking and one deposit charge exist for that request

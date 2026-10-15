@exp3 @validation @spec-exp3-L62-71 @rule-G1 @rule-G8
Feature: Malformed booking requests are refused identically by every stack
  As the experimenter comparing three stacks
  I want every stack to refuse the same malformed requests in the same way
  So that differences in the results come from the retry behaviour, not from input handling

  # Traces to: docs/exp3-spec.md lines 62-71, contract test 7, CLAUDE.md rules G1 and G8.
  # Rows tagged @open-question encode a proposed answer to a question the spec leaves open;
  # they are expected to fail on at least one stack today (see BDD_REVIEW.md, finding B11).

  Background:
    Given the booking service for the stack under test is running

  @contract-7 @failure
  Scenario Outline: A malformed booking is refused and nothing is recorded
    When the client sends a <endpoint> booking with <defect>
    Then the request is refused as invalid
    And no new booking or charge is recorded

    Examples: Covered today by contracts/tests/test_validation.py
      | endpoint | defect                      |
      | naive    | the owner missing           |
      | naive    | an unknown extra field      |
      | naive    | a negative deposit          |
      | naive    | a zero deposit              |
      | naive    | the deposit as quoted text  |
      | keyed    | the owner missing           |
      | keyed    | an unknown extra field      |
      | keyed    | a negative deposit          |
      | keyed    | a zero deposit              |
      | keyed    | the deposit as quoted text  |

    @open-question
    Examples: Not covered today; stacks are likely to disagree
      | endpoint | defect                          |
      | keyed    | an empty client reference       |
      | keyed    | a fractional deposit of 2500.5  |
      | keyed    | the deposit as true             |
      | keyed    | a null dog                      |
      | keyed    | field names in upper case       |
      | keyed    | a body that is not JSON         |

  @open-question @failure
  Scenario: A keyed booking with both a malformed body and no request key is refused for the body
    When the client sends a keyed booking with an unknown extra field and no request key
    Then the request is refused as invalid
    And no new booking or charge is recorded

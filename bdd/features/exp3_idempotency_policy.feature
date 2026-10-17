@exp3 @treatment @application @spec-exp3-L87-106
Feature: The idempotency policy decides create, replay, conflict or in-flight
  As the application layer that owns the idempotency policy
  I want every outcome decided from the stored request key alone
  So that each stack behaves identically without SQL, HTTP or framework types in the policy

  # Traces to: docs/exp3-spec.md lines 87-106 and CLAUDE.md (rules G2, G3).
  # Level: application service with the in-memory BookingStore (unit stage of each stack),
  # plus one inbound-adapter scenario with the driving port stubbed.

  @unit @happy
  Scenario: A fresh request key creates one booking and stores its result
    Given no booking has been made with request key "k1"
    When the service books with request key "k1"
    Then the outcome is a new booking
    And request key "k1" stores that booking's confirmation and request fingerprint

  @unit @inflight @spec-exp3-L100-101
  Scenario: A claimed request key with no stored result is reported as in flight
    Given request key "k1" is claimed for the same request but has no stored result
    When the service books with request key "k1"
    Then the outcome is in flight
    And no booking or charge is recorded

  @unit @failure @atomicity @rule-G3
  Scenario: A booking that fails part-way leaves no trace
    Given recording the deposit charge will fail once
    When the service books with request key "k1"
    Then the booking fails
    And no booking, no charge and no claim on request key "k1" remain

  @unit @failure @atomicity @rule-G3
  Scenario: A request key from a failed attempt can be used again
    Given an earlier booking with request key "k1" failed part-way
    When the service books with request key "k1"
    Then the outcome is a new booking
    And exactly one booking and one deposit charge exist for request key "k1"

  @adapter @inflight @spec-exp3-L100-101
  Scenario: An in-flight outcome tells the client to retry after one second
    Given the booking use case will report request key "k1" as in flight
    When the client books with request key "k1"
    Then the client is told the booking is still in flight and to retry after 1 second
    And the in-flight anomaly appears in the service log

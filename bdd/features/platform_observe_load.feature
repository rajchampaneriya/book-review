@platform
Feature: make observe-load fills the overlay's dashboard with known traffic
  As the operator showing the observability overlay
  I want a short, fixed mix of bookings on every running stack
  So that every application and business panel has data I can check against what was sent

  # Traces to: platform plan section 3.3 (the dashboard) and rule G8. Not a
  # measurement (rule H1): the load writes nothing to results/. The first
  # scenario needs no cluster. The others need the cluster from make up, the
  # stacks from make deploy and the overlay from make observe-up, and no other
  # booking traffic while they run, because they compare the outcome counters
  # with exactly what the load sent.

  @rule-G2
  Scenario: The load sends a fixed mix of new, replayed, conflicting and naive bookings
    Given an observe-load run of 5 minutes
    When the load is planned for one stack
    Then it sends 300 new keyed bookings and 100 replays of them
    And it sends 15 conflicting bookings and 10 bookings without a key
    And it sends 150 naive bookings

  @rule-G8
  Scenario: A short load fills the request, error and latency panels for every stack
    Given the observability overlay is on for every stack
    When the operator runs observe-load for 90 seconds
    Then the requests panel shows keyed and naive bookings for every stack
    And the errors panel shows conflicts and missing keys for every stack
    And the latency panel shows a p95 for every stack

  @rule-G2
  Scenario: The outcome counters rise by exactly what the load sent
    Given the observability overlay is on for every stack
    And the outcome counters have settled
    When the operator runs observe-load for 90 seconds
    Then every stack's created, replayed and conflict counters rose by what the load sent

  @spec-run-matrix
  Scenario: The load skips a stack the matrix scaled to 0
    Given the observability overlay is on for every stack
    And the matrix has scaled python to 0 replicas
    When the operator runs observe-load for 10 seconds
    Then the load reports python as skipped
    And java and dotnet answered every booking the load sent

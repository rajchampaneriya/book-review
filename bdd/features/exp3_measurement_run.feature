@exp3 @harness @spec-exp3-L121-153
Feature: Measured runs produce trustworthy evidence
  As the author who will publish duplicate counts
  I want every measured run to start clean, load a serving stack and refuse to record a failed run
  So that results/exp3 only ever holds valid measurements

  # Traces to: docs/exp3-spec.md lines 121-164 (load, measurement, run matrix, output files)
  # and CLAUDE.md rule H1. Level: harness/*.py with kubectl, k6 and Postgres replaced by
  # in-process fakes, so these scenarios run in seconds without a cluster.

  @matrix @regression @failure
  Scenario Outline: Only the stack under test serves traffic during its runs
    Given the matrix has finished measuring <earlier>
    When the matrix starts measuring <stack>
    Then <stack> has 1 replica
    And every other stack has 0 replicas

    Examples:
      | earlier       | stack  |
      | no stack yet  | dotnet |

    @known-defect
    Examples: Known defect, the stack under test is never scaled back to 1 (harness/exp3_matrix.py:115-121)
      | earlier       | stack  |
      | dotnet        | java   |
      | java          | python |

  @run @failure
  Scenario: A run in which no booking was recorded is rejected, not appended
    Given the stack under test answers no requests
    When a measured run completes
    Then the run is reported as invalid
    And no row is appended to the run log

  @run @happy
  Scenario: A measured run starts from empty tables
    Given the stack's tables hold bookings from an earlier run
    When a measured run starts
    Then the stack's bookings, charges and request keys are empty before load begins

  @run @happy
  Scenario Outline: Duplicates and losses are counted in the database
    Given a run sent <logical> logical requests
    And the database holds <total> bookings for <distinct> distinct client references
    When the run is counted
    Then the run records <duplicates> duplicate bookings and <lost> lost requests

    Examples:
      | logical | total | distinct | duplicates | lost |
      | 10000   | 10500 | 10000    | 500        | 0    |
      | 10000   | 10000 | 10000    | 0          | 0    |
      | 10000   | 9990  | 9990     | 0          | 10   |

  @load @edge
  Scenario Outline: The same logical requests are faulted in every stack and run
    When <total> logical requests are planned at a <rate> fault rate
    Then exactly <faulted> first attempts carry the fault header
    And the faulted request numbers are the same for every stack and run

    Examples:
      | total | rate | faulted |
      | 10000 | 0    | 0       |
      | 10000 | 0.01 | 100     |
      | 10000 | 0.05 | 500     |

  @matrix @happy
  Scenario: A resumed matrix skips runs already recorded for this commit
    Given the run log holds all 18 dotnet runs for the current commit
    When the matrix is planned
    Then 36 runs are planned
    And dotnet is not warmed up again

  @matrix @happy
  Scenario: A dry run plans the matrix without touching the cluster
    When the matrix is planned as a dry run
    Then 54 runs and 3 warm-ups are listed with an estimated duration
    And no cluster or load command is executed

  @matrix @happy
  Scenario: The matrix suspends the duplicate audit while it measures
    Given the duplicate-audit CronJob exists on its schedule
    When the matrix runs
    Then the audit is suspended before the first measured run
    And the audit is resumed after the last one

  @open-question @run
  Scenario: Switching fault injection on keeps the warmed-up process
    Given the stack under test has been warmed up
    When fault injection is switched on for a measured run
    Then the measured run is served by the warmed-up process

  @hostinfo @failure
  Scenario: Host details name the machine architecture
    Given the host is an arm64 machine
    When host details are captured
    Then the operating-system entry ends with "(arm64)"

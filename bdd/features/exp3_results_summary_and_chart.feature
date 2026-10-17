@exp3 @results @spec-exp3-L155-177 @rule-H1 @rule-H4
Feature: The summary and chart are derived only from valid, full-length runs of one commit
  As the author who will put the chart in an article
  I want the summary and chart to reflect exactly the measured runs of one commit
  So that no stale, smoke or synthetic number can reach a reader

  # Traces to: docs/exp3-spec.md lines 155-177 and CLAUDE.md rules H1 and H4.
  # Level: harness/exp3_summary.py and figures/exp3_duplicates.py on fixture files in tmp_path.

  # Known defect: harness/exp3_summary.py:36-38 groups every row regardless of commit or run length.
  @summary @failure @known-defect
  Scenario: Runs from other commits and shortened smoke runs are left out
    Given the run log holds 3 full-length runs of dotnet naive at 5% for commit A
    And a 500-request smoke run of dotnet naive at 5% for commit A
    And 1 full-length run of dotnet naive at 5% for commit B
    When the summary is built for commit A
    Then the dotnet naive 5% group summarises exactly the 3 full-length runs

  @summary @failure
  Scenario: The summary is refused while any run is invalid
    Given the run log holds a run that recorded no bookings
    When the summary is built
    Then the summary is refused and names that run
    And no summary file is written

  @summary @happy
  Scenario Outline: Each group reports the median and range of duplicates per 10,000 requests
    Given three full-length runs of a group recorded <duplicates> duplicate bookings out of 10000 logical requests
    When the summary is built
    Then the group's median is <median> per 10,000 and its range is <range>

    Examples:
      | duplicates  | median | range      |
      | 99, 100, 99 | 99.0   | 99.0-100.0 |
      | 0, 0, 0     | 0.0    | 0.0-0.0    |

  @summary @happy
  Scenario: The latency overhead of the request key is reported at fault rate 0
    Given dotnet runs at fault rate 0 have a median p99 of 8 ms naive and 10 ms keyed
    When the summary is built
    Then dotnet's p99 overhead is 2 ms

  @chart @happy
  Scenario: Every bar is labelled with its value, including zero
    Given a summary with every stack, variant and fault rate
    When the chart is drawn
    Then every bar is labelled with its median, including the keyed bars at 0.0

  # Known defect: figures/exp3_duplicates.py:60,68 draws a missing group as a 0 bar.
  @chart @failure @known-defect
  Scenario: A group with no data is shown as missing, not as zero
    Given a summary with no java rows at a 1% fault rate
    When the chart is drawn
    Then the java 1% bars are labelled "no data"

  @chart @failure @rule-H4
  Scenario: The synthetic fixture can never become the published chart
    Given the input is the labelled synthetic fixture
    When the chart is drawn to the published chart's location
    Then drawing is refused because the input is synthetic

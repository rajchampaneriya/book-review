@platform
Feature: Schemas land through an in-cluster Job and the audit never writes
  As the operator of the platform
  I want schemas applied by a Job and duplicates audited by a read-only CronJob
  So that no host-side kubectl exec touches the database and the audit cannot change what it counts

  # Traces to: platform plan sections 3.1 and 5 (step 4) and CLAUDE.md rule G7
  # (the audit must stay read-only). Both scenarios need the cluster from make
  # up with Postgres serving. The first re-applies the schemas and so wipes any
  # dev data in them; the second seeds the python schema and truncates it again
  # afterwards.

  @spec-infrastructure
  Scenario: Schemas are applied by an in-cluster Job
    Given the cluster from make up with Postgres serving
    When the rendered schema SQL is applied through the schema-apply Job
    Then the Job completes
    And the dotnet, java and python schemas each hold the three tables

  @spec-measurement
  Scenario: The duplicate audit never writes
    Given the python schema holds bookings with repeated client references
    When the duplicate-audit CronJob runs
    Then it reports the duplicate count
    And the row counts in every table are unchanged

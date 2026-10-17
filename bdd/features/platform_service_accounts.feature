@platform
Feature: The booking service holds no Kubernetes API credentials
  As the operator hardening the cluster
  I want the python service to run without an API identity
  So that a compromised service cannot inspect or change the cluster

  # Traces to: rule G7 and platform plan section 5, step 2.

  @rule-G7
  Scenario: The python service cannot use the Kubernetes API
    Given the python Deployment runs as the python service account
    When its permission to list pods in wcf-physics is checked
    Then the permission is denied
    And the pod has no API token mounted

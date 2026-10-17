# Four stages: build, unit, arch, runtime (docs/exp3-spec.md, Infrastructure).
FROM maven:3.9.16-eclipse-temurin-25 AS build
# OpenTelemetry Java agent for the observability overlay; versions checked on
# Maven Central 2026-10-17. The runtime image carries the jar, but the JVM loads
# it only when the overlay sets JAVA_TOOL_OPTIONS (infra/scripts/observe-up.sh).
ARG OTEL_JAVAAGENT_VERSION=2.32.0
WORKDIR /src
COPY . .
RUN mvn -B -q package -DskipTests \
    && mvn -B -q org.apache.maven.plugins:maven-dependency-plugin:3.11.0:copy \
       -Dartifact=io.opentelemetry.javaagent:opentelemetry-javaagent:${OTEL_JAVAAGENT_VERSION} \
       -DoutputDirectory=/otel -Dmdep.stripVersion=true

FROM build AS unit
RUN mvn -B test -pl booking-domain,booking-application

FROM build AS arch
# the spec's arch command (docs/exp3-spec.md, Architecture tests)
RUN mvn -B -pl booking-bootstrap -am test -Dtest=HexagonalArchitectureTest -Dsurefire.failIfNoSpecifiedTests=false

FROM eclipse-temurin:25-jre AS runtime
WORKDIR /app
COPY --from=build /src/booking-bootstrap/target/booking-bootstrap-0.1.0.jar app.jar
COPY --from=build /otel/opentelemetry-javaagent.jar /otel/opentelemetry-javaagent.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]

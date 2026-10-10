# Four stages: build, unit, arch, runtime (docs/exp3-spec.md, Infrastructure).
FROM maven:3.9.16-eclipse-temurin-25 AS build
WORKDIR /src
COPY . .
RUN mvn -B -q package -DskipTests

FROM build AS unit
RUN mvn -B test -pl booking-domain,booking-application

FROM build AS arch
# the spec's arch command (docs/exp3-spec.md, Architecture tests)
RUN mvn -B -pl booking-bootstrap -am test -Dtest=HexagonalArchitectureTest -Dsurefire.failIfNoSpecifiedTests=false

FROM eclipse-temurin:25-jre AS runtime
WORKDIR /app
COPY --from=build /src/booking-bootstrap/target/booking-bootstrap-0.1.0.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]

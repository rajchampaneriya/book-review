package work.rajc.booking.architecture;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.Architectures.layeredArchitecture;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

/**
 * Hexagonal architecture rules for the Java stack.
 *
 * <p>Copy verbatim to
 * booking-bootstrap/src/test/java/work/rajc/booking/architecture/HexagonalArchitectureTest.java.
 * tools/arch/check_hexagonal.py fails if the copy differs. The bootstrap module depends on every
 * other module, so its test classpath sees all production classes.
 *
 * <p>Requires test-scoped com.tngtech.archunit:archunit-junit5 in booking-bootstrap/pom.xml.
 */
@AnalyzeClasses(packages = "work.rajc.booking", importOptions = ImportOption.DoNotIncludeTests.class)
class HexagonalArchitectureTest {

    private static final String DOMAIN = "work.rajc.booking.domain..";
    private static final String APPLICATION = "work.rajc.booking.application..";
    private static final String APPLICATION_SERVICES = "work.rajc.booking.application.service..";
    private static final String ADAPTERS = "work.rajc.booking.adapter..";
    private static final String BOOTSTRAP = "work.rajc.booking.bootstrap..";

    /** Dependencies point inward: bootstrap > adapters > application > domain. Empty layers fail too. */
    @ArchTest
    static final ArchRule dependencies_point_inward = layeredArchitecture()
            .consideringOnlyDependenciesInLayers()
            .layer("Domain").definedBy(DOMAIN)
            .layer("Application").definedBy(APPLICATION)
            .layer("Adapters").definedBy(ADAPTERS)
            .layer("Bootstrap").definedBy(BOOTSTRAP)
            .whereLayer("Bootstrap").mayNotBeAccessedByAnyLayer()
            .whereLayer("Adapters").mayOnlyBeAccessedByLayers("Bootstrap")
            .whereLayer("Application").mayOnlyBeAccessedByLayers("Adapters", "Bootstrap")
            .whereLayer("Domain").mayOnlyBeAccessedByLayers("Application", "Adapters", "Bootstrap");

    /** Each adapter (in.http, out.postgres, ...) is its own slice; no slice may use another. */
    @ArchTest
    static final ArchRule adapters_do_not_depend_on_each_other = slices()
            .matching("work.rajc.booking.adapter.(*).(*)..")
            .should().notDependOnEachOther();

    /** Adapters call driving ports (application.port.in), never service implementations. */
    @ArchTest
    static final ArchRule adapters_use_ports_not_services = noClasses()
            .that().resideInAPackage(ADAPTERS)
            .should().dependOnClassesThat().resideInAPackage(APPLICATION_SERVICES);

    /** Ports are contracts: they never depend on the services that implement them. */
    @ArchTest
    static final ArchRule ports_do_not_depend_on_services = noClasses()
            .that().resideInAPackage("work.rajc.booking.application.port..")
            .should().dependOnClassesThat().resideInAPackage(APPLICATION_SERVICES);

    /** Frameworks and drivers live only in adapters and bootstrap. */
    @ArchTest
    static final ArchRule core_uses_no_frameworks_or_drivers = noClasses()
            .that().resideInAnyPackage(DOMAIN, APPLICATION)
            .should().dependOnClassesThat().resideInAnyPackage(
                    "org.springframework..",
                    "jakarta..",
                    "javax..",
                    "java.sql..",
                    "java.net..",
                    "com.zaxxer..",
                    "org.postgresql..",
                    "com.fasterxml..");
}

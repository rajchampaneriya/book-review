package work.rajc.booking.bootstrap;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.jackson.autoconfigure.JsonMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.support.JdbcTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import tools.jackson.databind.cfg.CoercionAction;
import tools.jackson.databind.cfg.CoercionInputShape;
import work.rajc.booking.adapter.in.http.FaultHook;
import work.rajc.booking.adapter.out.postgres.PostgresBookingStore;
import work.rajc.booking.application.port.in.BookSessionIdempotentUseCase;
import work.rajc.booking.application.port.in.BookSessionNaiveUseCase;
import work.rajc.booking.application.port.out.BookingStore;
import work.rajc.booking.application.service.BookSessionIdempotentService;
import work.rajc.booking.application.service.BookSessionNaiveService;

import javax.sql.DataSource;

@Configuration
public class UseCaseConfiguration {

    @Bean
    public BookingStore bookingStore(DataSource dataSource,
                                      JdbcClient jdbcClient,
                                      @Value("${app.database-schema:java}") String schema) {
        TransactionTemplate transactions = new TransactionTemplate(new JdbcTransactionManager(dataSource));
        return new PostgresBookingStore(jdbcClient, transactions, schema);
    }

    @Bean
    public BookSessionNaiveUseCase bookSessionNaiveUseCase(BookingStore store) {
        return new BookSessionNaiveService(store);
    }

    @Bean
    public BookSessionIdempotentUseCase bookSessionIdempotentUseCase(BookingStore store) {
        return new BookSessionIdempotentService(store);
    }

    @Bean
    public FaultHook faultHook(@Value("${app.fault-injection:}") String faultInjection,
                               @Value("${app.fault-hold-ms:2000}") long faultHoldMs) {
        return new FaultHook("enabled".equals(faultInjection), faultHoldMs);
    }

    @Bean
    public JsonMapperBuilderCustomizer strictNumbers() {
        // G1: a quoted number (deposit_cents: "2500") is a type error, not a value
        return builder -> builder.withCoercionConfigDefaults(config ->
                config.setCoercion(CoercionInputShape.String, CoercionAction.Fail));
    }
}

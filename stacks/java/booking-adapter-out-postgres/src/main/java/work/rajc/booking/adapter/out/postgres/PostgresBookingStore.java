package work.rajc.booking.adapter.out.postgres;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.transaction.support.TransactionTemplate;
import work.rajc.booking.application.port.out.BookingStore;
import work.rajc.booking.application.port.out.BookingTransaction;
import work.rajc.booking.application.port.out.KeyAlreadyClaimedException;
import work.rajc.booking.application.port.out.StoredKey;

import java.sql.SQLException;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;

/**
 * Plain SQL through JdbcClient, one transaction per use case (rule G3) via a
 * TransactionTemplate that lives here in the adapter, never as @Transactional
 * in the application. SQLSTATE 23505 is translated into the port's
 * KeyAlreadyClaimedException; no driver type crosses the port.
 */
public class PostgresBookingStore implements BookingStore {

    private static final ObjectMapper JSON = new ObjectMapper();
    private static final TypeReference<Map<String, String>> RESULT_TYPE = new TypeReference<>() {
    };

    private final JdbcClient jdbcClient;
    private final TransactionTemplate transactions;
    private final String schema;

    public PostgresBookingStore(JdbcClient jdbcClient, TransactionTemplate transactions, String schema) {
        this.jdbcClient = jdbcClient;
        this.transactions = transactions;
        this.schema = schema;
    }

    @Override
    public Optional<StoredKey> findKey(String key) {
        return jdbcClient.sql("SELECT key, request_hash, result FROM " + schema + ".idempotency_keys WHERE key = :key")
                .param("key", key)
                .query((rs, rowNum) -> {
                    Map<String, String> result = null;
                    String json = rs.getString("result");
                    if (json != null) {
                        try {
                            result = JSON.readValue(json, RESULT_TYPE);
                        } catch (JsonProcessingException e) {
                            throw new IllegalStateException("stored result is not valid JSON", e);
                        }
                    }
                    return new StoredKey(rs.getString("key"), rs.getString("request_hash"), result);
                })
                .optional();
    }

    @Override
    public <T> T inTransaction(Function<BookingTransaction, T> work) {
        try {
            return transactions.execute(status -> work.apply(new PostgresBookingTransaction(jdbcClient, schema)));
        } catch (DuplicateKeyException e) {
            if (isUniqueViolation(e)) {
                throw new KeyAlreadyClaimedException(e.getMessage());
            }
            throw e;
        }
    }

    private static boolean isUniqueViolation(DataAccessException e) {
        Throwable cause = e.getCause();
        return cause instanceof SQLException sql && "23505".equals(sql.getSQLState());
    }
}

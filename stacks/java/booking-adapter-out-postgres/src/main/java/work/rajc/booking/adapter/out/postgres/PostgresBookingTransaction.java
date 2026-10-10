package work.rajc.booking.adapter.out.postgres;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import work.rajc.booking.application.port.out.BookingTransaction;
import work.rajc.booking.domain.Booking;
import work.rajc.booking.domain.Charge;

import java.util.Map;

final class PostgresBookingTransaction implements BookingTransaction {

    private static final ObjectMapper JSON = new ObjectMapper();

    private final JdbcClient client;
    private final String schema;

    PostgresBookingTransaction(JdbcClient client, String schema) {
        this.client = client;
        this.schema = schema;
    }

    @Override
    public void claimKey(String key, String requestHash) {
        client.sql("INSERT INTO " + schema + ".idempotency_keys (key, request_hash) VALUES (:key, :request_hash)")
                .param("key", key)
                .param("request_hash", requestHash)
                .update();
    }

    @Override
    public void addBooking(Booking booking) {
        client.sql("INSERT INTO " + schema + ".bookings (id, client_ref, session_id, dog_id, owner_id, deposit_cents)"
                        + " VALUES (:id, :client_ref, :session_id, :dog_id, :owner_id, :deposit_cents)")
                .param("id", booking.id())
                .param("client_ref", booking.clientRef())
                .param("session_id", booking.sessionId())
                .param("dog_id", booking.dogId())
                .param("owner_id", booking.ownerId())
                .param("deposit_cents", booking.deposit().cents())
                .update();
    }

    @Override
    public void addCharge(Charge charge) {
        client.sql("INSERT INTO " + schema + ".charges (id, booking_id, client_ref, amount_cents)"
                        + " VALUES (:id, :booking_id, :client_ref, :amount_cents)")
                .param("id", charge.id())
                .param("booking_id", charge.bookingId())
                .param("client_ref", charge.clientRef())
                .param("amount_cents", charge.amountCents())
                .update();
    }

    @Override
    public void storeResult(String key, Map<String, String> result) {
        String json;
        try {
            json = JSON.writeValueAsString(result);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("result is not serialisable", e);
        }
        client.sql("UPDATE " + schema + ".idempotency_keys SET result = CAST(:result AS jsonb) WHERE key = :key")
                .param("key", key)
                .param("result", json)
                .update();
    }
}

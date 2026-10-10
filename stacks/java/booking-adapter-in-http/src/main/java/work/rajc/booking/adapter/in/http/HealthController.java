package work.rajc.booking.adapter.in.http;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class HealthController {

    private final String stack;

    public HealthController(@Value("${app.stack:java}") String stack) {
        this.stack = stack;
    }

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "ok", "stack", stack);
    }
}

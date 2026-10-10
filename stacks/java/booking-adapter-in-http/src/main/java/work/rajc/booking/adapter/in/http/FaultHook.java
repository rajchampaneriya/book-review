package work.rajc.booking.adapter.in.http;

import jakarta.servlet.http.HttpServletRequest;

/**
 * The fault hook: a transport concern living in the inbound HTTP adapter.
 * Called after the use case has returned (the commit has happened) and before
 * the response is written; a no-op unless enabled and the request carries
 * X-Fault: hold-after-commit, then holds the response (Thread.sleep; the
 * default platform-thread Tomcat makes that the stack's blocking wait) so the
 * client times out on a booking that is already committed.
 */
public final class FaultHook {

    private final boolean enabled;
    private final long holdMs;

    public FaultHook(boolean enabled, long holdMs) {
        this.enabled = enabled;
        this.holdMs = holdMs;
    }

    public void afterCommit(HttpServletRequest request) {
        if (enabled && "hold-after-commit".equals(request.getHeader("X-Fault"))) {
            try {
                Thread.sleep(holdMs);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }
}

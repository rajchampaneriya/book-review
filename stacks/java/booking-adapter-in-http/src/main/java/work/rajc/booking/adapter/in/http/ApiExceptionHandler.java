package work.rajc.booking.adapter.in.http;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import work.rajc.booking.domain.InvalidDepositException;

/** Invalid JSON (unknown or missing fields, wrong types) and an invalid deposit -> 400 invalid_request. */
@RestControllerAdvice
public class ApiExceptionHandler {

    @ExceptionHandler({HttpMessageNotReadableException.class, InvalidDepositException.class})
    public ResponseEntity<ErrorResponse> invalidRequest(Exception e) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(new ErrorResponse("invalid_request"));
    }
}

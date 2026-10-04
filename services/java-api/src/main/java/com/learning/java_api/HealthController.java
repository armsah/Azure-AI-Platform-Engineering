package com.learning.java_api;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

@RestController
public class HealthController {

    private final RestClient restClient = RestClient.create();

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of(
                "status", "healthy",
                "service", "java-api");
    }

    @GetMapping("/trace-demo")
    public Map<String, Object> traceDemo() {
        String nodeUrl = System.getenv()
                .getOrDefault("NODE_API_URL", "http://localhost:3000");

        Object downstream = restClient
                .get()
                .uri(nodeUrl + "/health")
                .retrieve()
                .body(Object.class);

        return Map.of(
                "service", "java-api",
                "downstream", downstream);
    }
}
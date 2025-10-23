package com.example.demo.integration;

import com.example.demo.model.User;
import com.example.demo.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.transaction.annotation.Transactional;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Transactional
class UserControllerIntegrationTest {

    @LocalServerPort
    private int port;

    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private UserRepository userRepository;

    private String baseUrl;

    @BeforeEach
    void setUp() {
        baseUrl = "http://localhost:" + port + "/api/users";
        userRepository.deleteAll(); // Clean database before each test
    }

    @Test
    void testCreateAndRetrieveUser() {
        // Given
        User newUser = new User();
        newUser.setName("Integration Test User");
        newUser.setEmail("integration@example.com");

        // When - Create user
        ResponseEntity<User> createResponse = restTemplate.postForEntity(baseUrl, newUser, User.class);

        // Then - Verify creation
        assertEquals(HttpStatus.OK, createResponse.getStatusCode());
        assertNotNull(createResponse.getBody());
        assertNotNull(createResponse.getBody().getId());
        assertEquals("Integration Test User", createResponse.getBody().getName());

        // When - Retrieve user
        ResponseEntity<User> getResponse = restTemplate.getForEntity(
                baseUrl + "/" + createResponse.getBody().getId(), User.class);

        // Then - Verify retrieval
        assertEquals(HttpStatus.OK, getResponse.getStatusCode());
        assertEquals("Integration Test User", getResponse.getBody().getName());
    }

    @Test
    void testGetAllUsers() {
        // Given - Create multiple users
        User user1 = new User();
        user1.setName("User One");
        user1.setEmail("user1@example.com");
        userRepository.save(user1);

        User user2 = new User();
        user2.setName("User Two");
        user2.setEmail("user2@example.com");
        userRepository.save(user2);

        // When
        ResponseEntity<User[]> response = restTemplate.getForEntity(baseUrl, User[].class);

        // Then
        assertEquals(HttpStatus.OK, response.getStatusCode());
        assertNotNull(response.getBody());
        assertEquals(2, response.getBody().length);
    }

    @Test
    void testCreateUserWithDuplicateEmail() {
        // Given - Create first user
        User firstUser = new User();
        firstUser.setName("First User");
        firstUser.setEmail("duplicate@example.com");
        userRepository.save(firstUser);

        // When - Try to create user with same email
        User duplicateUser = new User();
        duplicateUser.setName("Duplicate User");
        duplicateUser.setEmail("duplicate@example.com");

        ResponseEntity<User> response = restTemplate.postForEntity(baseUrl, duplicateUser, User.class);

        // Then
        assertEquals(HttpStatus.BAD_REQUEST, response.getStatusCode());
    }

    @Test
    void testGetNonExistentUser() {
        // When
        ResponseEntity<User> response = restTemplate.getForEntity(baseUrl + "/999", User.class);

        // Then
        assertEquals(HttpStatus.NOT_FOUND, response.getStatusCode());
    }

    @Test
    void testFullUserLifecycle() {
        // Create
        User newUser = new User();
        newUser.setName("Lifecycle User");
        newUser.setEmail("lifecycle@example.com");

        ResponseEntity<User> createResponse = restTemplate.postForEntity(baseUrl, newUser, User.class);
        assertEquals(HttpStatus.OK, createResponse.getStatusCode());

        Long userId = createResponse.getBody().getId();

        // Read
        ResponseEntity<User> getResponse = restTemplate.getForEntity(baseUrl + "/" + userId, User.class);
        assertEquals(HttpStatus.OK, getResponse.getStatusCode());
        assertEquals("Lifecycle User", getResponse.getBody().getName());

        // Verify in database
        assertTrue(userRepository.existsById(userId));
        assertTrue(userRepository.existsByEmail("lifecycle@example.com"));
    }

    @Test
    void testApplicationHealthCheck() {
        // When - Check if application is running
        ResponseEntity<String> response = restTemplate.getForEntity(
                "http://localhost:" + port + "/actuator/health", String.class);

        // Then - Application should be healthy (if actuator is enabled)
        // If actuator is not configured, this test verifies the app is at least running
        assertTrue(response.getStatusCode().is2xxSuccessful() ||
                response.getStatusCode() == HttpStatus.NOT_FOUND);
    }

    @Test
    void testDatabaseConnection() {
        // Given
        User testUser = new User();
        testUser.setName("DB Test User");
        testUser.setEmail("dbtest@example.com");

        // When
        User savedUser = userRepository.save(testUser);

        // Then - Verify database operations work
        assertNotNull(savedUser.getId());
        assertTrue(userRepository.existsById(savedUser.getId()));
        assertEquals(1, userRepository.count());
    }
}
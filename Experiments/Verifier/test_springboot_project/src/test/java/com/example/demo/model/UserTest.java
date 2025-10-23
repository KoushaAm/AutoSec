package com.example.demo.model;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class UserTest {

    private User user;

    @BeforeEach
    void setUp() {
        user = new User();
    }

    @Test
    void testUserCreation() {
        // Given & When
        User newUser = new User();

        // Then
        assertNotNull(newUser);
        assertNull(newUser.getId());
        assertNull(newUser.getName());
        assertNull(newUser.getEmail());
    }

    @Test
    void testSettersAndGetters() {
        // Given
        Long expectedId = 1L;
        String expectedName = "John Doe";
        String expectedEmail = "john@example.com";

        // When
        user.setId(expectedId);
        user.setName(expectedName);
        user.setEmail(expectedEmail);

        // Then
        assertEquals(expectedId, user.getId());
        assertEquals(expectedName, user.getName());
        assertEquals(expectedEmail, user.getEmail());
    }

    @Test
    void testEqualsAndHashCode() {
        // Given
        User user1 = new User();
        user1.setId(1L);
        user1.setName("John Doe");
        user1.setEmail("john@example.com");

        User user2 = new User();
        user2.setId(1L);
        user2.setName("John Doe");
        user2.setEmail("john@example.com");

        User user3 = new User();
        user3.setId(2L);
        user3.setName("Jane Smith");
        user3.setEmail("jane@example.com");

        // Then
        assertEquals(user1, user2);
        assertNotEquals(user1, user3);
        assertEquals(user1.hashCode(), user2.hashCode());
        assertNotEquals(user1.hashCode(), user3.hashCode());
    }

    @Test
    void testToString() {
        // Given
        user.setId(1L);
        user.setName("John Doe");
        user.setEmail("john@example.com");

        // When
        String userString = user.toString();

        // Then
        assertNotNull(userString);
        assertTrue(userString.contains("John Doe"));
        assertTrue(userString.contains("john@example.com"));
    }

    @Test
    void testEmailValidation() {
        // Given
        user.setEmail("valid@example.com");

        // When & Then
        assertEquals("valid@example.com", user.getEmail());

        // Test edge cases
        user.setEmail("");
        assertEquals("", user.getEmail());

        user.setEmail(null);
        assertNull(user.getEmail());
    }

    @Test
    void testNameValidation() {
        // Given & When
        user.setName("Valid Name");

        // Then
        assertEquals("Valid Name", user.getName());

        // Test edge cases
        user.setName("");
        assertEquals("", user.getName());

        user.setName(null);
        assertNull(user.getName());
    }
}
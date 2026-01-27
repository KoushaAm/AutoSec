package com.example.demo.repository;

import com.example.demo.model.User;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

@DataJpaTest
class UserRepositoryTest {

    @Autowired
    private TestEntityManager entityManager;

    @Autowired
    private UserRepository userRepository;

    private User testUser1;
    private User testUser2;

    @BeforeEach
    void setUp() {
        testUser1 = new User();
        testUser1.setName("John Doe");
        testUser1.setEmail("john@example.com");

        testUser2 = new User();
        testUser2.setName("Jane Smith");
        testUser2.setEmail("jane@example.com");
    }

    @Test
    void testSaveUser() {
        // When
        User savedUser = userRepository.save(testUser1);

        // Then
        assertNotNull(savedUser);
        assertNotNull(savedUser.getId());
        assertEquals("John Doe", savedUser.getName());
        assertEquals("john@example.com", savedUser.getEmail());
    }

    @Test
    void testFindById() {
        // Given
        User savedUser = entityManager.persistAndFlush(testUser1);

        // When
        Optional<User> foundUser = userRepository.findById(savedUser.getId());

        // Then
        assertTrue(foundUser.isPresent());
        assertEquals("John Doe", foundUser.get().getName());
        assertEquals("john@example.com", foundUser.get().getEmail());
    }

    @Test
    void testFindById_NotFound() {
        // When
        Optional<User> foundUser = userRepository.findById(999L);

        // Then
        assertFalse(foundUser.isPresent());
    }

    @Test
    void testFindAll() {
        // Given
        entityManager.persistAndFlush(testUser1);
        entityManager.persistAndFlush(testUser2);

        // When
        List<User> users = userRepository.findAll();

        // Then
        assertEquals(2, users.size());
        assertTrue(users.stream().anyMatch(u -> "John Doe".equals(u.getName())));
        assertTrue(users.stream().anyMatch(u -> "Jane Smith".equals(u.getName())));
    }

    @Test
    void testExistsByEmail() {
        // Given
        entityManager.persistAndFlush(testUser1);

        // When & Then
        assertTrue(userRepository.existsByEmail("john@example.com"));
        assertFalse(userRepository.existsByEmail("nonexistent@example.com"));
    }

    @Test
    void testDeleteUser() {
        // Given
        User savedUser = entityManager.persistAndFlush(testUser1);
        Long userId = savedUser.getId();

        // When
        userRepository.deleteById(userId);
        entityManager.flush();

        // Then
        Optional<User> deletedUser = userRepository.findById(userId);
        assertFalse(deletedUser.isPresent());
    }

    @Test
    void testUpdateUser() {
        // Given
        User savedUser = entityManager.persistAndFlush(testUser1);

        // When
        savedUser.setName("Updated Name");
        savedUser.setEmail("updated@example.com");
        User updatedUser = userRepository.save(savedUser);
        entityManager.flush();

        // Then
        assertEquals("Updated Name", updatedUser.getName());
        assertEquals("updated@example.com", updatedUser.getEmail());
    }

    @Test
    void testUserPersistence() {
        // Given
        User user = new User();
        user.setName("Persistence Test");
        user.setEmail("persist@example.com");

        // When
        User savedUser = userRepository.save(user);
        entityManager.flush();
        entityManager.clear(); // Clear persistence context

        User retrievedUser = userRepository.findById(savedUser.getId()).orElse(null);

        // Then
        assertNotNull(retrievedUser);
        assertEquals("Persistence Test", retrievedUser.getName());
        assertEquals("persist@example.com", retrievedUser.getEmail());
    }
}
package example;

/**
 * Handles authentication and login validation.
 * Responsible for verifying user credentials.
 */
public class AuthManager {

    // Validate login credentials
    public boolean validateUser(String username, String password) {
        return username != null && password != null;
    }

    // Generate authentication token
    public String generateToken(String username) {
        return username + "_token";
    }
}
package example;

/**
 * Service responsible for user management operations.
 * Handles profile updates and score updates.
 */
public class UserService {

    private int userScore;

    // Update score for a specific user
    public void updateUserScore(String userId, int score) {
        System.out.println("Updating score for user: " + userId);
        this.userScore = score;
    }

    // Retrieve stored user score
    public int getUserScore() {
        return userScore;
    }
}
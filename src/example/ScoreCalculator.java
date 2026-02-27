package example;

/**
 * Calculates score values based on user activity.
 * Performs score computation logic.
 */
public class ScoreCalculator {

    // Calculate score using activity points
    public int calculateScore(int activityPoints) {
        int totalScore = activityPoints * 10;
        return totalScore;
    }

    // Apply bonus score
    public int applyBonus(int score) {
        return score + 50;
    }
}
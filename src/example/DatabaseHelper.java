package example;

/**
 * Provides database connection utilities.
 * Executes queries and manages data storage.
 */
public class DatabaseHelper {

    // Open database connection
    public void connectDatabase() {
        System.out.println("Database connected");
    }

    // Execute query operation
    public void executeQuery(String query) {
        System.out.println("Executing query: " + query);
    }
}
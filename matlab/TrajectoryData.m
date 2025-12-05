file_path = 'C:\Users\munib\Documents\PandasForGVS\NOV29PILOT\AS_CONTDATA_PILOT_NOV_29_2023_OCULUS_CLEAN.csv';

data_table = readtable(file_path, 'Delimiter', ',');


% Use readtable to import the CSV file with a comma as the delimiter
data_table = readtable(file_path, 'Delimiter', ',');

% Access the 'TF' column from the table
tf_column = data_table.TF;

% Initialize the 'targetHit' column with zeros
data_table.targetHit = zeros(size(tf_column));

% Find the indices where 'true' changes to 'false'
change_indices = find(strcmp(tf_column, 'False') & [false; strcmp(tf_column(1:end-1), 'True')]);

% Update the 'targetHit' column at change indices to 0, and 1 otherwise
data_table.targetHit(change_indices) = 0;
data_table.targetHit(~ismember(1:numel(tf_column), change_indices)) = 1;

% Access the rows where 'targetHit' is '0'
rows_with_target_hit_0 = data_table(data_table.targetHit == 0, :);
  
% Determine the number of rows
num_rows = size(rows_with_target_hit_0, 1);

% Specify the chunk size (e.g., 20 rows per chunk)
chunk_size = 20;

% Initialize a cell array to store the data variables
data_cells = cell(1, ceil(num_rows / chunk_size));

% Separate every 20 rows into different data variables
for i = 1:chunk_size:num_rows
    end_idx = min(i + chunk_size - 1, num_rows);
    data_cells{ceil(i / chunk_size)} = rows_with_target_hit_0(i:end_idx, :);
end

% Plot scatter plots for each individual chunk
figure;
for i = 1:numel(data_cells)
    subplot(ceil(numel(data_cells)/2), 2, i); % Adjust subplot layout
    scatter(data_cells{i}.HandX, data_cells{i}.HandY);
    title(['Chunk ', num2str(i)]);
    xlabel('X Axis Label');
    ylabel('Y Axis Label');
    xlim([-0.1, 0.1]);
    ylim([0.9, 1.1]);
end

% Adjust figure layout
sgtitle('Scatter Plots of Individual Chunks');


% Initialize variables to store results
average_x_values = zeros(1, numel(data_cells));
average_y_values = zeros(1, numel(data_cells));
average_x_error = zeros(1, numel(data_cells));
average_y_error = zeros(1, numel(data_cells));
overall_error = zeros(1, numel(data_cells));

% Calculate averages and errors for each chunk
for i = 1:numel(data_cells)
    % Extract x and y values from the current chunk
    chunk_data = data_cells{i};
    x_values = chunk_data.HandX;
    y_values = chunk_data.HandY;

    % Calculate average x and y values
    average_x_values(i) = mean(x_values);
    average_y_values(i) = mean(y_values);

    % Calculate x and y errors from the center of the plane (0,1)
    x_errors = x_values - 0;
    y_errors = y_values - 0.97;

    % Calculate average x and y errors
    average_x_error(i) = mean(x_errors);
    average_y_error(i) = mean(y_errors);

    % Calculate overall error
    overall_error(i) = mean(sqrt(x_errors.^2 + y_errors.^2));
end

% Display results
disp('Results:');
disp('Chunk | Avg X | Avg Y | Avg X Error | Avg Y Error | Overall Error');
for i = 1:numel(data_cells)
    fprintf('%5d | %6.4f | %6.4f | %10.4f | %10.4f | %13.4f\n', i, ...
        average_x_values(i), average_y_values(i), ...
        average_x_error(i), average_y_error(i), overall_error(i));
end

% Initialize variables to store results
average_x_values = zeros(1, numel(data_cells));
average_y_values = zeros(1, numel(data_cells));
average_x_error = zeros(1, numel(data_cells));
average_y_error = zeros(1, numel(data_cells));
overall_error = zeros(1, numel(data_cells));

% Calculate averages and errors for each chunk
for i = 1:numel(data_cells)
    % Extract x and y values from the current chunk
    chunk_data = data_cells{i};
    x_values = chunk_data.HandX;
    y_values = chunk_data.HandY;

    % Calculate average x and y values
    average_x_values(i) = mean(x_values);
    average_y_values(i) = mean(y_values);

    % Calculate x and y errors from the center of the plane (0,1)
    x_errors = x_values - 0;
    y_errors = y_values - 0.97;

    % Calculate average x and y errors
    average_x_error(i) = mean(x_errors);
    average_y_error(i) = mean(y_errors);

    % Calculate overall error
    overall_error(i) = mean(sqrt(x_errors.^2 + y_errors.^2));
end

% Plot scatter plots for each individual chunk with averages and errors
figure;
for i = 1:numel(data_cells)
    subplot(ceil(numel(data_cells)/2), 2, i);
    scatter(data_cells{i}.HandX, data_cells{i}.HandY);
    hold on;

    % Plot average point
    scatter(average_x_values(i), average_y_values(i), 50, 'r', 'filled', 'MarkerEdgeColor', 'k');

    % Plot error bars for x and y
    errorbar(average_x_values(i), average_y_values(i), average_x_error(i), 'horizontal', 'LineStyle', 'none', 'Color', 'k');
    errorbar(average_x_values(i), average_y_values(i), average_y_error(i), 'vertical', 'LineStyle', 'none', 'Color', 'k');

    title(['Chunk ', num2str(i)]);
    xlabel('X Axis Label');
    ylabel('Y Axis Label');
    xlim([-0.1, 0.1]);
    ylim([0.87, 1.07]);

    hold off;
end

% Adjust figure layout
sgtitle('Scatter Plots with Averages and Errors');

% ... (Previous code remains unchanged)
% Specify circular target bullseye center and radius
target_center = [0, 0.97];  % Center coordinates [x, y]
target_radius = 0.05;  % Radius of the circular target

% Initialize a variable to count points within the target
points_in_target_count = 0;

% Loop through all data points in all chunks
for i = 1:numel(data_cells)
    chunk_data = data_cells{i};
    
    % Check if each point is within the circular target
    within_target = sqrt((chunk_data.HandX - target_center(1)).^2 + (chunk_data.HandY - target_center(2)).^2) <= target_radius;
    
    % Update the count of points within the target
    points_in_target_count = points_in_target_count + sum(within_target);
end


% Calculate the proportion of points within the target
all_data = vertcat(data_cells{:});
proportion_in_target = points_in_target_count / size(all_data, 1);


% Display the proportion
fprintf('Proportion of points within the circular target: %.4f\n', proportion_in_target);

% Plot scatter plots for all chunks with circular target bullseye
figure;
for i = 1:numel(data_cells)
    subplot(ceil(numel(data_cells)/2), 2, i);
    scatter(data_cells{i}.HandX, data_cells{i}.HandY);
    hold on;

    % Plot circular target bullseye
    rectangle('Position', [target_x_range(1), target_y_range(1), target_x_range(2)-target_x_range(1), target_y_range(2)-target_y_range(1)],...
        'Curvature', [1,1], 'EdgeColor', 'r');

    % Mark points within the target as green
    within_target = (data_cells{i}.HandX >= target_x_range(1) & data_cells{i}.HandX <= target_x_range(2)) ...
        & (data_cells{i}.HandY >= target_y_range(1) & data_cells{i}.HandY <= target_y_range(2));
    scatter(data_cells{i}.HandX(within_target), data_cells{i}.HandY(within_target), 50, 'g', 'filled');

    title(['Chunk ', num2str(i)]);
    xlabel('X Axis Label');
    ylabel('Y Axis Label');
    xlim([-0.1, 0.1]);
    ylim([0.9, 1.1]);

    hold off;
end

% Adjust figure layout
sgtitle('Scatter Plots with Circular Target ');


% ... (Previous code remains unchanged)

% Loop through all data cells and create a scatter plot window for each chunk
for i = 1:numel(data_cells)
    % Create a new figure for each chunk
    figure;
    
    % Scatter plot for the current chunk
    scatter(data_cells{i}.HandX, data_cells{i}.HandY);
    hold on;

    % Plot circular target bullseye
    rectangle('Position', [target_x_range(1), target_y_range(1), target_x_range(2)-target_x_range(1), target_y_range(2)-target_y_range(1)],...
        'Curvature', [1,1], 'EdgeColor', 'r');

    % Mark points within the target as green
    within_target = (data_cells{i}.HandX >= target_x_range(1) & data_cells{i}.HandX <= target_x_range(2)) ...
        & (data_cells{i}.HandY >= target_y_range(1) & data_cells{i}.HandY <= target_y_range(2));
    
    green_dots_count = sum(within_target); % Count the number of green dots
    
    scatter(data_cells{i}.HandX(within_target), data_cells{i}.HandY(within_target), 50, 'g', 'filled');

    title(['Scatter Plot for Chunk ', num2str(i), ' - Green Dots: ', num2str(green_dots_count)]);
    xlabel('X Axis Label');
    ylabel('Y Axis Label');
    xlim([-0.1, 0.1]);
    ylim([0.9, 1.1]);

    hold off;
end



%Create printable viewable graphs
%Out of the 20 hits, what are the proportion hit 
%proportion right
%normalize data
%histograms of error in x and y
%anova

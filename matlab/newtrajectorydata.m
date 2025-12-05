% close all
% clc

file_path = 'C:\Users\munib\Documents\PandasForGVS\NOV29PILOT\AS_CONTDATA_PILOT_NOV_29_2023_OCULUS_CLEAN.csv';
data_table = readtable(file_path, 'Delimiter', ',');

% Access the 'HandX', 'HandY' and 'HandZ' columns from the table
hand_x_column = data_table.HandX;
hand_y_column = data_table.HandY;
hand_z_column = data_table.HandZ;


% Calculate the center and radius of the bullseye based on the entire dataset
bullseye_center = [0, 0.97];
bullseye_radius = 0.005;

% Initialize the 'targetHit' column with zeros
data_table.targetHit = zeros(size(hand_x_column));

% Find the indices where 'true' changes to 'false'
change_indices = find(strcmp(data_table.TF, 'False') & [false; strcmp(data_table.TF(1:end-1), 'True')]);

% Update the 'targetHit' column at change indices to 0, and 1 otherwise
data_table.targetHit(change_indices) = 0; 
data_table.targetHit(~ismember(1:numel(data_table.TF), change_indices)) = 1;

% Access the rows where 'targetHit' is '0'
rows_with_target_hit_0 = data_table(data_table.targetHit == 0, :);

% Determine the number of rows
num_rows = size(rows_with_target_hit_0, 1);

% Specify the chunk size (e.g., 20 rows per chunk)
chunk_size = 20;

% Set x and y axis ranges for scatter plots
x_range = [-0.07, 0.07];
y_range = [0.92, 1.02];

% Initialize a cell array to store the data variables
data_cells = cell(1, ceil(num_rows / chunk_size));

% Separate every 20 rows into different data variables
for i = 1:chunk_size:num_rows
    end_idx = min(i + chunk_size - 1, num_rows);
    
    % Include 'HandX' and 'HandY' columns in the data_cells
    chunk_data = rows_with_target_hit_0(i:end_idx, :);
    
    % Calculate distance from the bullseye center
    distances = sqrt((chunk_data.HandX - bullseye_center(1)).^2 + (chunk_data.HandY - bullseye_center(2)).^2);
    
    % Count the number of points within the bullseye area
    points_in_bullseye = sum(distances <= bullseye_radius);
    
    % Display the count of points in the bullseye for the current chunk
    fprintf('Chunk %d: %d points in the bullseye\n', ceil(i / chunk_size), points_in_bullseye);
    
    % Calculate the portion of targets greater than and less than x = 0
    portion_right = sum(chunk_data.HandX > 0) / numel(chunk_data.HandX);
    portion_left = sum(chunk_data.HandX < 0) / numel(chunk_data.HandX);
    
    % Display the portions
    fprintf('Portion right: %.2f\n', portion_right);
    fprintf('Portion left: %.2f\n', portion_left);
    
    % Create a scatter plot for the current chunk with color coordination
    figure;
    scatter(chunk_data.HandX, chunk_data.HandY, [], linspace(0, 1, numel(chunk_data.HandX)), 'Marker', 'o');
    colorbar;
    hold on;
    
    % Mark the bullseye area with a red circle
    theta = linspace(0, 2*pi, 100);
    bullseye_x = bullseye_center(1) + bullseye_radius * cos(theta);
    bullseye_y = bullseye_center(2) + bullseye_radius * sin(theta);
    plot(bullseye_x, bullseye_y, 'r-', 'LineWidth', 2);
    
    % Set x and y axis ranges
    xlim(x_range);
    ylim(y_range);
    
    title(['Scatter plot for Chunk ', num2str(ceil(i / chunk_size))]);
    xlabel('HandX');
    ylabel('HandY');
    legend('All points', 'Bullseye area');
    hold off;
    
    % Store the chunk data in data_cells
    data_cells{ceil(i / chunk_size)} = chunk_data;
end

% Plot frequency histograms for each individual chunk in a new window
for i = 1:numel(data_cells)
    figure; % Create a new figure for each chunk
    histogram(data_cells{i}.HandX, 'BinWidth', 0.005, 'Normalization', 'probability');
    title(['Frequency Histogram of Chunk ', num2str(i)]);
    xlabel('HandX Values');
    ylabel('Frequency');
    xlim([-0.1, 0.1]);
end



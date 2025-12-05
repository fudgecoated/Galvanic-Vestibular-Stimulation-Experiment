file_path = 'C:\Users\munib\Documents\PandasForGVS\NOV29PILOT\AS_CONTDATA_PILOT_NOV_29_2023_OCULUS_CLEAN.csv';
data_table = readtable(file_path, 'Delimiter', ',');


% Assuming 'TF' is a column in the data_table
% Create a logical vector indicating where 'TF' goes from 'True' to 'False'
transition_indices = [strcmp(data_table.TF(1:end-1), 'True') & strcmp(data_table.TF(2:end), 'False'); false];

% Initialize the 'reachEnd' column with zeros
data_table.reachEnd = zeros(size(data_table, 1), 1);

% Assign the value of 1 to the row before the transition occurs
data_table.reachEnd(transition_indices) = 1;

% Create a logical vector indicating rows where 'TF' is 'False'
false_indices = strcmp(data_table.TF, 'False');

% Remove rows where 'TF' is 'False'
data_table = data_table(~false_indices, :);

% Assuming 'reachEnd' is a column in the data_table
reachEnd_indices = find(data_table.reachEnd == 1); % Find indices where 'reachEnd' is 1

% Initialize a grouping variable
grouping_var = zeros(size(data_table, 1), 1);



% Assuming 'reachEnd' is a column in the data_table
% Initialize 'reachNum' column with zeros
data_table.reachNum = zeros(size(data_table, 1), 1);

% Find the indices where 'reachEnd' is equal to 1
reach_end_indices = find(data_table.reachEnd == 1);

% Increment the 'reachNum' value each time 'reachEnd' is equal to 1
for i = 1:length(reach_end_indices)
    data_table.reachNum(reach_end_indices(i):end) = data_table.reachNum(reach_end_indices(i):end) + 1;
end
% Assuming 'reachNum' is a column in the data_table

% Find the indices where 'reachNum' changes
change_indices = [0; diff(data_table.reachNum) ~= 0];

% Group indices based on 'reachNum'
groups = findgroups(cumsum(change_indices));

% Define a function to extract grouped tables
extract_grouped_table = @(varargin) {table(varargin{:})};

% Split the data_table into groups based on 'reachNum'
grouped_tables = splitapply(extract_grouped_table, data_table, groups);

% If needed, you can access individual tables using grouped_tables{1}, grouped_tables{2}, etc.

% Assuming grouped_tables is the cell array of table arrays
% Assuming data_table is the original table

% Determine the number of groups
num_groups = ceil(length(grouped_tables) / 20);

% Initialize cell array for grouped data
final_grouped_data = cell(num_groups, 1);

% Ensure all tables in grouped_tables have the same column names as data_table
for i = 1:length(grouped_tables)
    grouped_tables{i}.Properties.VariableNames = data_table.Properties.VariableNames;
    % Delete the first row in each sub-table
    grouped_tables{i}(1,:) = [];
end

% Group every 20 elements
for i = 1:num_groups
    start_index = (i - 1) * 20 + 1;
    end_index = min(i * 20, length(grouped_tables));
    final_grouped_data{i} = vertcat(grouped_tables{start_index:end_index});
end


% Initialize a cell array for measured distances
measured_distance = cell(length(grouped_tables), 1);

% Iterate through each sub-table in grouped_tables
for i = 1:length(grouped_tables)
    % Extract HandZ variable values from the current sub-table
    HandZ_values = grouped_tables{i}.HandZ;
    
    % Find the difference between the first and last HandZ value
    distance = HandZ_values(end) - HandZ_values(1);
    
    % Store the difference in measured_distance table
    measured_distance{i} = table(distance, 'VariableNames', {'MeasuredDistance'});
end

% Initialize variables to store results
max_handz_difference = zeros(length(grouped_tables), 1);
max_handz_difference_seconds = zeros(length(grouped_tables), 1);
first_last_handz_difference = zeros(length(grouped_tables), 1);
corresponding_handz_value = zeros(length(grouped_tables), 1);
first_last_seconds_difference = zeros(length(grouped_tables), 1);

% Iterate through each sub-table
for i = 1:length(grouped_tables)
    % Calculate the difference between the first and last 'HandZ' variable value
    first_handz = grouped_tables{i}.HandZ(1);
    last_handz = grouped_tables{i}.HandZ(end);
    first_last_handz_difference(i) = last_handz - first_handz;
    
    % Find the biggest difference between consecutive rows in 'HandZ' variable
    handz_differences = diff(grouped_tables{i}.HandZ);
    [max_diff, max_diff_index] = max(abs(handz_differences));
    
    % Find the corresponding 'HandZ' value
    corresponding_handz_value(i) = grouped_tables{i}.HandZ(max_diff_index + 1);
    
    % Find the corresponding difference in 'seconds' variable
    corresponding_seconds_diff = grouped_tables{i}.seconds(max_diff_index + 1) - grouped_tables{i}.seconds(max_diff_index);
    
    % Calculate the difference between the first and last 'seconds' variable value
    first_seconds = grouped_tables{i}.seconds(1);
    last_seconds = grouped_tables{i}.seconds(end);
    first_last_seconds_difference(i) = last_seconds - first_seconds;
    
    % Store results
    max_handz_difference(i) = max_diff;
    max_handz_difference_seconds(i) = corresponding_seconds_diff;
end

% Create a new table to store results
results_table = table(max_handz_difference, corresponding_handz_value, max_handz_difference_seconds, first_last_handz_difference, first_last_seconds_difference);

% Calculate speed for max_handz_difference
results_table.max_handz_speed = results_table.max_handz_difference ./ results_table.max_handz_difference_seconds;

% Calculate speed for first_last_handz_difference
results_table.first_last_handz_speed = results_table.first_last_handz_difference ./ results_table.first_last_seconds_difference;

writetable(results_table,'velocity_reach.csv') 



% Initialize a cell array to store grouped tables
grouped_result_tables = {};

% Group every 20 rows
num_groups = ceil(height(results_table) / 20);
for i = 1:num_groups
    start_index = (i - 1) * 20 + 1;
    end_index = min(i * 20, height(results_table));
    grouped_result_tables{i} = results_table(start_index:end_index, :);
end

% Concatenate the tables into a single table
grouped_results_table = vertcat(grouped_result_tables{:});

new_averages = {};

for i = 1:num_groups
    for


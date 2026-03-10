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


% Initialize variables to store maximum and minimum values
max_values = [];
min_values = [];

% Iterate over each sub-table in grouped_tables
for i = 1:length(grouped_tables)
    % Extract 'HandX' and 'seconds' columns from the current sub-table
    HandX_values = grouped_tables{i}.HandX;
    seconds_values = grouped_tables{i}.seconds;
    
    % Calculate maximum and minimum values of 'HandX'
    max_handx = max(HandX_values);
    min_handx = min(HandX_values);
    
    % Find corresponding 'seconds' values
    max_seconds_index = find(HandX_values == max_handx, 1);
    min_seconds_index = find(HandX_values == min_handx, 1);
    max_seconds_index = find(HandX_values == max_handx, 1);
    min_seconds_index = find(HandX_values == min_handx, 1);


    % Extract 'seconds' values
    max_seconds = seconds_values(max_seconds_index);
    min_seconds = seconds_values(min_seconds_index);
    
    % Store the maximum and minimum values and corresponding 'seconds' values
    max_values = [max_values; max_handx, max_seconds];
    min_values = [min_values; min_handx, min_seconds];
end

% Create a table containing maximum and minimum values along with corresponding 'seconds'
result_table = table(max_values(:,1), max_values(:,2), min_values(:,1), min_values(:,2), ...
                     'VariableNames', {'Max_HandX', 'Max_seconds', 'Min_HandX', 'Min_seconds'});

writetable(result_table, "max_min_x_trajectory.csv")
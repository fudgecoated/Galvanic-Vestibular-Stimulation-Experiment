% Load your data file (replace 'your_data_file.csv' with your actual file name)
data = readtable('gvsmatlabfiles\matlab.mat');

% Extract rows where 'TF' column is true
selectedRows = data(data.TF == true, :);

% Select specific columns
selectedData = selectedRows(:, {'HandX', 'HandY', 'HandZ', 'seconds'});

% Save the selected data to a new file (replace 'selected_data_file.csv' with your desired file name)
writetable(selectedData, 'TrueTrials.csv');

disp('Selected data has been saved to "selected_data_file.csv"');

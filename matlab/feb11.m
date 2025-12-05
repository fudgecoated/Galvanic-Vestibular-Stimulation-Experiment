    % covariance of x with y
%             n=100; % Number of points around ellipse
%             p=0:pi/n:2*pi; % angles around a circle
%             C = cov([rx(idx_tmp) ry(idx_tmp)]); % covariance of rx and ry
%             [eigvec,eigval] = eig(C) % Compute eigen-stuff
%             xy = [cos(p'),sin(p')] * sqrt(eigval) * eigvec'; % Transformation
%             x_ellips = xy(:,1) + mean(rx(idx_tmp));
%             y_ellips = xy(:,2) + mean(ry(idx_tmp));
%             plot(x_ellips,y_ellips,'ro')
%             axis equal

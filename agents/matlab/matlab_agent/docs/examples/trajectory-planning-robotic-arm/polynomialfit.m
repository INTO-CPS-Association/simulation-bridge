function a = polynomialfit(q0,qf,dq0,dqf,ddq0,ddqf,t0,tf,n)
    if n < 5
        disp("Error: n >= 5")
        a = [];
    else
        A = zeros(6,n+1);

        for j = 1:n+1
            A(1,j) = t0^(n+1-j);
            A(2,j) = tf^(n+1-j);
            if n-j >= 0
                A(3,j) = (n+1-j)*t0^(n-j);
                A(4,j) = (n+1-j)*tf^(n-j);
            end
            if n-j-1 >= 0
                A(5,j) = (n+1-j)*(n-j)*t0^(n-j-1);
                A(6,j) = (n+1-j)*(n-j)*tf^(n-j-1);    
            end
        end
        
        b = [q0;qf;dq0;dqf;ddq0;ddqf];
        a = A\b;
end